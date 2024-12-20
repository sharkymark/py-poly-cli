import requests
import sys
import urllib.parse
from halo import Halo
from datetime import datetime
import sqlite3
from dateutil import parser
import os
from gnews import GNews

def init_db():
    conn = sqlite3.connect('weather_history.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS searches
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  address TEXT,
                  matched_address TEXT,
                  lat REAL,
                  lon REAL,
                  timestamp DATETIME)''')
    conn.commit()
    conn.close()

def save_search(address, location_data):
    conn = sqlite3.connect('weather_history.db')
    c = conn.cursor()
    c.execute('''INSERT INTO searches (address, matched_address, lat, lon, timestamp)
                 VALUES (?, ?, ?, ?, ?)''',
                 (address, 
                  location_data['matched_address'],
                  location_data['lat'],
                  location_data['lon'],
                  datetime.now()))
    conn.commit()
    conn.close()

def get_coordinates(address):
    """Convert address to coordinates using Census Geocoding API"""
    encoded_address = urllib.parse.quote(address)
    census_url = f"https://geocoding.geo.census.gov/geocoder/locations/onelineaddress?address={encoded_address}&benchmark=2020&format=json"
    
    spinner = Halo('Looking up address...')
    spinner.start()
    try:
        response = requests.get(census_url)
        response.raise_for_status()
        data = response.json()
        
        if data['result']['addressMatches']:
            match = data['result']['addressMatches'][0]
            return {
                'lat': match['coordinates']['y'],
                'lon': match['coordinates']['x'],
                'matched_address': match['matchedAddress']
            }
        else:
            return None
    except Exception as e:
        print(f"Error getting coordinates: {e}")
        return None
    finally:
        spinner.stop()

def get_weather(lat, lon):
    """Get weather data from National Weather Service API"""
    spinner = Halo('Getting weather data...')
    spinner.start()
    try:
        # First, get the grid coordinates
        point_url = f"https://api.weather.gov/points/{lat},{lon}"
        response = requests.get(point_url)
        response.raise_for_status()
        grid_data = response.json()
        
        # Then get the forecast data using the grid coordinates
        forecast_url = grid_data['properties']['forecast']
        response = requests.get(forecast_url)
        response.raise_for_status()
        weather_data = response.json()
        
        current_period = weather_data['properties']['periods'][0]
        forecast_periods = weather_data['properties']['periods'][1:4]  # Next 3 periods
        
        return {
            'current': {
                'temperature': current_period['temperature'],
                'unit': current_period['temperatureUnit'],
                'forecast': current_period['shortForecast'],
                'wind': current_period['windSpeed'] + ' ' + current_period['windDirection'],
                'humidity': current_period.get('relativeHumidity', {}).get('value', 'N/A'),
            },
            'forecast': forecast_periods
        }
    except Exception as e:
        print(f"Error getting weather: {e}")
        return None
    finally:
        spinner.stop()

def get_google_maps_url(address):
    """Generate Google Maps URL for the address"""
    encoded_address = urllib.parse.quote(address)
    return f"https://www.google.com/maps/search/?api=1&query={encoded_address}"

def display_weather(location_data, weather_data):
    """Display weather results"""
    maps_url = get_google_maps_url(location_data['matched_address'])
    
    print("\nResults:")
    print(f"Matched Address: {location_data['matched_address']}")
    print("\nCurrent Conditions:")
    print(f"Temperature: {weather_data['current']['temperature']}°{weather_data['current']['unit']}")
    print(f"Conditions: {weather_data['current']['forecast']}")
    print(f"Wind: {weather_data['current']['wind']}")
    if weather_data['current']['humidity'] != 'N/A':
        print(f"Humidity: {weather_data['current']['humidity']}%")
    
    print("\nUpcoming Forecast:")
    for period in weather_data['forecast']:
        print(f"\n{period['name']}:")
        print(f"  Temperature: {period['temperature']}°{period['temperatureUnit']}")
        print(f"  Conditions: {period['shortForecast']}")
        print(f"  Wind: {period['windSpeed']} {period['windDirection']}")
    
    print(f"\nView on Google Maps: {maps_url}")

def lookup_weather():
    """Handle weather lookup logic"""
    address = input("\nEnter address (street, city, state, zip code): ")
    
    # Get coordinates
    spinner = Halo('Looking up address...')
    spinner.start()
    location_data = get_coordinates(address)
    spinner.stop()
    
    if location_data is None:
        print("\nError: Could not find the address. Please check and try again.")
        return
    
    # Get weather
    weather_data = get_weather(location_data['lat'], location_data['lon'])
    
    if weather_data is None:
        print("\nError: Could not retrieve weather data.")
        return
    
    display_weather(location_data, weather_data)
    
    if location_data:
        save_search(address, location_data)

def get_saved_addresses():
    conn = sqlite3.connect('weather_history.db')
    c = conn.cursor()
    c.execute('''SELECT DISTINCT address, matched_address, lat, lon, MAX(timestamp) as latest
                 FROM searches 
                 GROUP BY matched_address
                 ORDER BY latest DESC''')
    addresses = c.fetchall()
    conn.close()
    return addresses

def select_saved_address():
    addresses = get_saved_addresses()
    if not addresses:
        print("\nNo saved addresses found.")
        return
    
    print("\nSaved addresses:")
    for i, (address, matched_address, lat, lon, _) in enumerate(addresses, 1):
        print(f"{i}. {matched_address}")
    
    choice = input("\nSelect address number (or 0 to go back): ")
    try:
        choice = int(choice)
        if choice == 0:
            return
        if 1 <= choice <= len(addresses):
            _, matched_address, lat, lon, _ = addresses[choice-1]
            location_data = {
                'matched_address': matched_address,
                'lat': lat,
                'lon': lon
            }
            weather_data = get_weather(lat, lon)
            if weather_data:
                display_weather(location_data, weather_data)
            input("\nPress Enter to continue...")
        else:
            print("\nInvalid selection.")
    except ValueError:
        print("\nPlease enter a valid number.")

def weather_menu():
    """Display and handle weather submenu"""
    while True:
        print("\n=== Weather Lookup Menu ===")
        print("1. Enter new address")
        print("2. Select from saved addresses")
        print("3. Return to main menu")
        
        choice = input("\nEnter your choice (1-3): ")
        
        if choice == "1":
            lookup_weather()
        elif choice == "2":
            select_saved_address()
        elif choice == "3":
            return
        else:
            print("\nInvalid choice. Please enter 1-3.")

def get_nfl_scores():
    """Fetch NFL scores from ESPN API"""
    spinner = Halo('Getting NFL scores...')
    spinner.start()
    try:
        url = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        if not data.get('events'):
            print("\nNo NFL games found.")
            return
        
        print("\nNFL Scores:")
        print("-" * 50)
        
        for event in data['events']:
            game_status = event['status']['type']['state']
            competition = event['competitions'][0]
            home_team = competition['competitors'][0]
            away_team = competition['competitors'][1]
            
            # Format based on game status
            if game_status == 'pre':
                game_time = event['status']['type']['shortDetail']
                print(f"{away_team['team']['displayName']} @ {home_team['team']['displayName']}")
                print(f"Starting: {game_time}")
            else:
                home_score = home_team['score']
                away_score = away_team['score']
                
                if game_status == 'in':
                    period = event['status']['type']['shortDetail']
                    print(f"{away_team['team']['displayName']} {away_score} @ {home_team['team']['displayName']} {home_score}")
                    print(f"Current: {period}")
                else:  # post-game
                    print(f"Final: {away_team['team']['displayName']} {away_score} @ {home_team['team']['displayName']} {home_score}")
            
            print("-" * 50)
        
    except Exception as e:
        print(f"\nError getting NFL scores: {e}")
    finally:
        spinner.stop()
    
    input("\nPress Enter to continue...")

def nfl_menu():
    """Display and handle NFL scores menu"""
    while True:
        print("\n=== NFL Scores Menu ===")
        print("1. View latest scores")
        print("2. Return to main menu")
        
        choice = input("\nEnter your choice (1-2): ")
        
        if choice == "1":
            get_nfl_scores()
        elif choice == "2":
            return
        else:
            print("\nInvalid choice. Please enter 1-2.")

def get_news(domain=None):
    """Fetch news articles using GNews"""
    spinner = Halo('Fetching news articles...')
    spinner.start()
    
    try:
        # Initialize GNews with default settings
        google_news = GNews(language='en', country='US', period='1d', max_results=5)
        
        # Set default domain to wsj.com if none provided
        domain = domain or 'wsj.com'
        
        # Use the correct method to fetch articles by site
        articles = google_news.get_news_by_site(domain)
        
        if not articles:
            print(f"\nNo articles found for domain: {domain}")
            return
            
        print(f"\nLatest news from {domain}:")
        print("-" * 80)
        
        for article in articles:
            # Parse and format the date
            pub_date = parser.parse(article['published date'])
            friendly_date = pub_date.strftime("%B %d, %Y at %I:%M %p")
            
            print(f"Title: {article['title']}")
            print(f"Published: {friendly_date}")
            print(f"URL: {article['url']}")
            print("-" * 80)
            
    except Exception as e:
        print(f"\nUnexpected error: {e}")
    finally:
        spinner.stop()
    
    input("\nPress Enter to continue...")

def news_menu():
    """Display and handle news menu"""
    while True:
        print("\n=== News Menu ===")
        print("1. Get news from WSJ")
        print("2. Get news from specific domain")
        print("3. Return to main menu")
        
        choice = input("\nEnter your choice (1-3): ")
        
        if choice == "1":
            get_news()  # Will use default wsj.com
        elif choice == "2":
            domain = input("\nEnter domain (e.g., wsj.com): ")
            get_news(domain)
        elif choice == "3":
            return
        else:
            print("\nInvalid choice. Please enter 1-3.")

def main_menu():
    """Display and handle main menu"""
    init_db()  # Ensure database exists
    while True:
        print("\n=== Multi-Service CLI Tool ===")
        print("1. Weather Lookup")
        print("2. NFL Scores")
        print("3. News")
        print("4. Quit")
        
        choice = input("\nEnter your choice (1-4): ")
        
        if choice == "1":
            weather_menu()
        elif choice == "2":
            nfl_menu()
        elif choice == "3":
            news_menu()
        elif choice == "4":
            print("\nGoodbye!")
            sys.exit(0)
        else:
            print("\nInvalid choice. Please enter 1-4.")

if __name__ == "__main__":
    main_menu()