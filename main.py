import psycopg2
import requests
import time
import os

# ----------------------
# CONFIGURATION
# ----------------------

APPIDS = {
    730: 'Counter-Strike 2',
    570: 'Dota 2',
    440: 'Team Fortress 2',
    578080: 'PUBG',
    1172470: 'Apex Legends',
    2767030: 'Marvel Rivals'
}

# PostgreSQL Database Connection from Environment Variables
DB_CONFIG = {
    # Railway PostgreSQL host
    'host': os.getenv('DB_HOST'),
    # Railway PostgreSQL database
    'database': os.getenv('DB_DATABASE'),
    # PostgreSQL username
    'user': os.getenv('DB_USER'),
    # PostgreSQL password
    'password': os.getenv('DB_PASSWORD'),
    # Default PostgreSQL port (can be overridden)
    'port': os.getenv('DB_PORT', 5432)
}

# Steam Web API Key
STEAM_API_KEY = os.getenv('STEAM_API_KEY')  # Your Steam Web API key

# ----------------------
# DB INIT
# ----------------------

def init_db():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    # Create games table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS games (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        )
    ''')

    # Create player_counts table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS player_counts (
            id SERIAL PRIMARY KEY,
            game_id INTEGER REFERENCES games(id),
            timestamp INTEGER,
            player_count INTEGER,
            on_sale BOOLEAN,
            discount_percent INTEGER,
            original_price INTEGER,
            final_price INTEGER,
            estimated_owners TEXT
        )
    ''')

    # Insert/update games
    for appid, name in APPIDS.items():
        cur.execute('INSERT INTO games (id, name) VALUES (%s, %s) ON CONFLICT (id) DO NOTHING', (appid, name))

    conn.commit()
    cur.close()
    conn.close()
    return

# ----------------------
# GET PLAYER COUNT
# ----------------------

def get_current_player_count(appid):
    url = 'https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/'
    try:
        response = requests.get(url, params={'appid': appid, 'key': STEAM_API_KEY})
        data = response.json()
        return data['response'].get('player_count', 0)
    except Exception as e:
        print(f"Error fetching player count for {appid}: {e}")
        return 0

# ----------------------
# GET SALE INFO
# ----------------------

def get_sale_info(appid):
    url = f'https://store.steampowered.com/api/appdetails'
    try:
        response = requests.get(url, params={'appids': appid, 'key': STEAM_API_KEY, 'cc': 'us', 'l': 'en'})
        data = response.json()
        app_data = data[str(appid)]
        if app_data['success']:
            details = app_data['data']
            if 'price_overview' in details:
                price = details['price_overview']
                return {
                    'on_sale': price['discount_percent'] > 0,
                    'discount_percent': price['discount_percent'],
                    'original_price': price['initial'],
                    'final_price': price['final']
                }
        return {
            'on_sale': False,
            'discount_percent': 0,
            'original_price': None,
            'final_price': None
        }
    except Exception as e:
        print(f"Error fetching sale info for {appid}: {e}")
        return {
            'on_sale': False,
            'discount_percent': 0,
            'original_price': None,
            'final_price': None
        }

# ----------------------
# GET ESTIMATED OWNERS
# ----------------------

def get_estimated_owners(appid):
    try:
        url = f'https://steamspy.com/api.php?request=appdetails&appid={appid}'
        response = requests.get(url)
        data = response.json()
        return data.get('owners', "unknown")
    except Exception as e:
        print(f"Error fetching ownership info for {appid}: {e}")
        return "unknown"

# ----------------------
# LOG TO DATABASE
# ----------------------

def log_player_data(appid, player_count, sale_info, owners):
    timestamp = int(time.time())
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    cur.execute('''
        INSERT INTO player_counts (
            game_id, timestamp, player_count,
            on_sale, discount_percent, original_price, final_price,
            estimated_owners
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    ''', (
        appid, timestamp, player_count,
        sale_info['on_sale'],
        sale_info['discount_percent'],
        sale_info['original_price'],
        sale_info['final_price'],
        owners
    ))

    conn.commit()
    cur.close()
    conn.close()
    return

# ----------------------
# TRACKING FUNCTION
# ----------------------

def track_games(appid_map):
    for appid, name in appid_map.items():
        print(f"\nTracking {name} (AppID: {appid})")

        count = get_current_player_count(appid)
        sale = get_sale_info(appid)
        owners = get_estimated_owners(appid)
        log_player_data(appid, count, sale, owners)

        print(f"- Players: {count}")
        print(f"- On Sale: {'Yes' if sale['on_sale'] else 'No'} ({sale['discount_percent']}% off)")
        print(f"- Price: {sale['final_price']} / {sale['original_price']} (cents)")
        print(f"- Owners: {owners}")
    return

# ----------------------
# MAIN
# ----------------------

if __name__ == '__main__':
    init_db()
    track_games(APPIDS)
