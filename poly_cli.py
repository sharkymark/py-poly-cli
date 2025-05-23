import requests
import sys
import urllib.parse
import argparse
from halo import Halo
from datetime import datetime
from datetime import datetime, timedelta
import sqlite3
from dateutil import parser
import sqlite3 # Ensure sqlite3 is imported to use its constants
import os
from gnews import GNews
import json
import math
from simple_salesforce import Salesforce, SalesforceAuthenticationFailed, SalesforceExpiredSession

# Parse command-line arguments
parser = argparse.ArgumentParser(description='Poly CLI - A multi-function command-line interface')
parser.add_argument('--debug', action='store_true', help='Enable debug mode with additional information')
args = parser.parse_args()

# Global debug flag
DEBUG_MODE = args.debug

# Global variables to store Salesforce credentials
sf_username = None
sf_password = None
sf_token = None
sf_instance = None

# Adapters for storing and retrieving datetime objects with SQLite
def adapt_datetime_iso(val):
    """Adapt datetime.datetime to ISO 8601 string."""
    return val.isoformat()

def convert_datetime_iso(val):
    """Convert ISO 8601 string to datetime.datetime object."""
    return datetime.fromisoformat(val.decode())

sqlite3.register_adapter(datetime, adapt_datetime_iso)
sqlite3.register_converter("DATETIME", convert_datetime_iso)

def init_db():
    conn = sqlite3.connect('history.db', detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS searches
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  address TEXT,
                  matched_address TEXT,
                  lat REAL,
                  lon REAL,
                  timestamp DATETIME)''')
    c.execute('''CREATE TABLE IF NOT EXISTS news_sites
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  url TEXT UNIQUE,
                  timestamp DATETIME)''')
    conn.commit()
    conn.close()

def save_search(address, location_data):
    conn = sqlite3.connect('history.db', detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
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

def save_news_site(url):
    """Save a news site URL to the database"""
    conn = sqlite3.connect('history.db', detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    c = conn.cursor()
    try:
        c.execute('''INSERT OR IGNORE INTO news_sites (url, timestamp)
                    VALUES (?, ?)''', (url, datetime.now()))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        conn.close()

def get_saved_news_sites():
    """Get all saved news site URLs from the database"""
    conn = sqlite3.connect('history.db', detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    c = conn.cursor()
    c.execute('''SELECT url FROM news_sites ORDER BY timestamp DESC''')
    sites = [row[0] for row in c.fetchall()]
    conn.close()
    return sites

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
    address = safe_input("\nEnter address (street, city, state, zip code): ")
    
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
    conn = sqlite3.connect('history.db', detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
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
    
    choice = safe_input("\nSelect address number (or 0 to go back): ")
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
            safe_input("\nPress Enter to continue...")
        else:
            print("\nInvalid selection.")
    except ValueError:
        print("\nPlease enter a valid number.")

def weather_menu():
    """Display and handle weather submenu"""
    while True:
        try:
            print("\n=== Weather Lookup Menu ===")
            print("1. Enter new address")
            print("2. Select from saved addresses")
            print("3. Return to main menu")
            
            choice = safe_input("\nEnter your choice (1-3): ")
            
            if choice == "1":
                lookup_weather()
            elif choice == "2":
                select_saved_address()
            elif choice == "3":
                return
            else:
                print("\nInvalid choice. Please enter 1-3.")
        except KeyboardInterrupt:
            exit_gracefully("\n\nProgram interrupted. Goodbye!")
        except EOFError:
            exit_gracefully("\n\nEnd of input. Goodbye!")

def get_sports_scores(sport, league, league_name):
    """Fetch sports scores from ESPN API for specified league"""
    spinner = Halo(f'Getting {league_name} scores...')
    spinner.start()
    try:
        url = f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        if not data.get('events'):
            print(f"\nNo {league_name} games found.")
            
            # Show debug info only when in debug mode
            if DEBUG_MODE:
                print(f"\n--- Debug Info ---")
                print(f"API URL: {url}")
                print(f"Data returned: {json.dumps(data, indent=2, default=str)[:500]}...")  # Show truncated data
            
            print("-" * 70)
            return
        
        print(f"\n{league_name} Scores:")
        print("-" * 50)
        
        for event in data['events']:
            game_status = event['status']['type']['state']
            competition = event['competitions'][0]
            home_team = competition['competitors'][0]
            away_team = competition['competitors'][1]
            
            # Get venue information if available (for all game states)
            venue_info = ""
            if competition.get('venue') and competition['venue'].get('fullName'):
                venue_name = competition['venue']['fullName']
                # Get city/state if available
                if competition['venue'].get('address') and competition['venue']['address'].get('city'):
                    venue_city = competition['venue']['address']['city']
                    venue_info = f"{venue_name}, {venue_city}"
                else:
                    venue_info = venue_name
            
            # Format based on game status
            if game_status == 'pre':
                # Use the detail field which contains the game time in local timezone
                # Detail example: "Sat, May 24th at 3:00 PM EDT"
                game_time = event['status']['type'].get('detail', event['status']['type'].get('shortDetail', 'Scheduled'))
                
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
            
            # Display venue info for all game states
            if venue_info.strip():
                print(f"Venue: {venue_info.strip()}")
            
            print("-" * 70)
        
        # Display debug info only in debug mode
        if DEBUG_MODE:
            print(f"--- Debug Info ---")
            print(f"API URL: {url}")
            
            # For MLS, show extra debug info about the response structure
            if league == "usa.1" and data.get('events'):
                print("\nMLS Debug: Sample event structure")
                sample_event = data['events'][0]
                print(f"Event date format: {sample_event.get('date', 'N/A')}")
                print(f"Status type: {json.dumps(sample_event.get('status', {}).get('type', {}), indent=2, default=str)}")
                print(f"League: {json.dumps(data.get('leagues', [{}])[0] if data.get('leagues') else {}, indent=2, default=str)[:200]}...")
                
    except Exception as e:
        print(f"\nError getting {league_name} scores: {e}")
        
        # Display debug info for troubleshooting even when there's an error, but only in debug mode
        if DEBUG_MODE:
            print(f"\n--- Debug Info ---")
            print(f"API URL: {url}")
            
        print("-" * 70)
    finally:
        spinner.stop()
    
    safe_input("\nPress Enter to continue...")

def get_nfl_scores():
    """Fetch NFL scores from ESPN API (legacy function for compatibility)"""
    get_sports_scores("football", "nfl", "NFL")

def scores_menu():
    """Display and handle sports scores menu"""
    while True:
        try:
            print("\n=== Sports Scores Menu ===")
            print("1. NFL")
            print("2. MLB")
            print("3. NHL")
            print("4. NBA")
            print("5. MLS")
            print("6. College Football")
            
            # Conditionally add the debug option
            if DEBUG_MODE:
                print("7. View Raw API Data")
                print("8. Return to main menu")
                max_option = 8
            else:
                print("7. Return to main menu")
                max_option = 7
            
            choice = safe_input(f"\nEnter your choice (1-{max_option}): ")
            
            if choice == "1":
                get_sports_scores("football", "nfl", "NFL")
            elif choice == "2":
                get_sports_scores("baseball", "mlb", "MLB")
            elif choice == "3":
                get_sports_scores("hockey", "nhl", "NHL")
            elif choice == "4":
                get_sports_scores("basketball", "nba", "NBA")
            elif choice == "5":
                get_sports_scores("soccer", "usa.1", "MLS")
            elif choice == "6":
                get_sports_scores("football", "college-football", "NCAA Football")
            elif choice == "7" and DEBUG_MODE:
                view_raw_sports_data_menu()
            elif (choice == "7" and not DEBUG_MODE) or (choice == "8" and DEBUG_MODE):
                return
            else:
                print(f"\nInvalid choice. Please enter 1-{max_option}.")
        except KeyboardInterrupt:
            exit_gracefully("\n\nProgram interrupted. Goodbye!")
        except EOFError:
            exit_gracefully("\n\nEnd of input. Goodbye!")

def view_raw_sports_data(sport, league, league_name):
    """View raw JSON data from the ESPN API for a specific league"""
    spinner = Halo(f'Fetching raw {league_name} API data...')
    spinner.start()
    try:
        url = f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        spinner.stop()
        
        print(f"\n=== Raw {league_name} API Data ===")
        print(f"API URL: {url}")
        print("\nJSON Response (first 1000 characters):")
        print("-" * 80)
        print(json.dumps(data, indent=2, default=str)[:1000])
        print("...")
        print("-" * 80)
        
        # Show important sections of the data structure
        if data.get('events'):
            print("\nImportant Data Fields:")
            print("-" * 80)
            print(f"Number of events: {len(data['events'])}")
            
            if len(data['events']) > 0:
                sample_event = data['events'][0]
                print(f"\nSample Event ID: {sample_event.get('id', 'N/A')}")
                print(f"Event Date: {sample_event.get('date', 'N/A')}")
                print(f"Status State: {sample_event.get('status', {}).get('type', {}).get('state', 'N/A')}")
                print(f"Status Detail: {sample_event.get('status', {}).get('type', {}).get('shortDetail', 'N/A')}")
        else:
            print("\nNo events found in the API response.")
        
    except Exception as e:
        spinner.fail(f"Error fetching {league_name} data: {e}")
    
    print("\n")
    safe_input("Press Enter to continue...")

def view_raw_sports_data_menu():
    """Display and handle raw sports data menu"""
    while True:
        try:
            print("\n=== View Raw Sports Data Menu ===")
            print("1. NFL")
            print("2. MLB")
            print("3. NHL")
            print("4. NBA")
            print("5. MLS")
            print("6. College Football")
            print("7. Return to sports scores menu")
            
            choice = safe_input("\nEnter your choice (1-7): ")
            
            if choice == "1":
                view_raw_sports_data("football", "nfl", "NFL")
            elif choice == "2":
                view_raw_sports_data("baseball", "mlb", "MLB")
            elif choice == "3":
                view_raw_sports_data("hockey", "nhl", "NHL")
            elif choice == "4":
                view_raw_sports_data("basketball", "nba", "NBA")
            elif choice == "5":
                view_raw_sports_data("soccer", "usa.1", "MLS")
            elif choice == "6":
                view_raw_sports_data("football", "college-football", "NCAA Football")
            elif choice == "7":
                return
            else:
                print("\nInvalid choice. Please enter 1-7.")
        except KeyboardInterrupt:
            exit_gracefully("\n\nProgram interrupted. Goodbye!")
        except EOFError:
            exit_gracefully("\n\nEnd of input. Goodbye!")

# Keep this for backward compatibility
def nfl_menu():
    """Redirects to the scores menu for backward compatibility"""
    scores_menu()

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
            return False
            
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
        
        # Save the domain to database if successful
        save_news_site(domain)
        return True
            
    except Exception as e:
        print(f"\nUnexpected error: {e}")
    finally:
        spinner.stop()
    
    safe_input("\nPress Enter to continue...")

def news_menu():
    """Display and handle news menu"""
    # Default news sites to include
    default_sites = ['wsj.com', 'washingtonpost.com', 'nytimes.com', 'apnews.com', 'whitehouse.gov']
    
    # Initialize default news sites in the database if they don't exist
    for site in default_sites:
        save_news_site(site)
    
    while True:
        try:
            # Get saved news sites from database
            all_sites = get_saved_news_sites()
            
            # Separate default sites from user-saved sites
            user_saved_sites = [site for site in all_sites if site not in default_sites]
            
            print("\n=== News Menu ===")
            
            # Display menu options
            print("1. Enter a new domain")
            print("2. Return to main menu")
            
            # Display default news sites section
            print("\n=== Default News Sites ===")
            next_index = 3
            for i, site in enumerate(default_sites, next_index):
                print(f"{i}. {site}")
            
            next_index += len(default_sites)
            
            # Display user-saved news sites section, if any
            if user_saved_sites:
                print("\n=== Saved News Sites ===")
                for i, site in enumerate(user_saved_sites, next_index):
                    print(f"{i}. {site}")
            
            # Add return to main menu at the bottom as well
            print(f"\n{next_index + len(user_saved_sites)}. Return to main menu")
            
            # Calculate total options
            total_options = 2 + len(default_sites) + len(user_saved_sites) + 1  # +1 for the extra return option
            choice = safe_input(f"\nEnter your choice (1-{total_options}): ")
            
            try:
                choice_num = int(choice)
                if choice_num == 1:
                    domain = safe_input("\nEnter domain (e.g., wsj.com): ")
                    if domain:
                        get_news(domain)
                elif choice_num == 2:
                    return
                elif 3 <= choice_num < 3 + len(default_sites):
                    # User selected a default site
                    selected_site = default_sites[choice_num - 3]
                    get_news(selected_site)
                elif 3 + len(default_sites) <= choice_num < total_options:
                    # User selected a saved site
                    selected_site = user_saved_sites[choice_num - (3 + len(default_sites))]
                    get_news(selected_site)
                elif choice_num == total_options:
                    # User selected the return to main menu option at the bottom
                    return
                else:
                    print(f"\nInvalid choice. Please enter 1-{total_options}.")
            except ValueError:
                print("\nInvalid input. Please enter a number.")
        except KeyboardInterrupt:
            exit_gracefully("\n\nProgram interrupted. Goodbye!")
        except EOFError:
            exit_gracefully("\n\nEnd of input. Goodbye!")

def get_bls_data(series_id):
    """Fetch data from BLS API for a given series ID"""
    url = f"https://api.bls.gov/publicAPI/v2/timeseries/data/{series_id}"
    headers = {'Content-type': 'application/json'}
    data = json.dumps({
        "seriesid": [series_id],
        "startyear": "2022",
        "endyear": "2023"
    })
    response = requests.post(url, headers=headers, data=data)
    response.raise_for_status()
    return response.json()

def display_bls_data():
    """Display economic indicators from BLS API"""
    # Removed global spinner initialization and start
    
    series_ids = {
        "CPI": "CUSR0000SA0",
        "CPI Less Food and Energy": "CUSR0000SA0L1E",
        "PPI": "PCUOMFG--OMFG--",
        "Nonfarm Payroll": "CES0000000001",
        "Unemployment Rate": "LNS14000000",
        "Employment in Residential Construction": "CES2023610001"
    }
    
    for name, series_id in series_ids.items():
        spinner = Halo(text=f'Fetching {name}...', spinner='dots')
        spinner.start()
        try:
            data = get_bls_data(series_id) # This function calls response.raise_for_status()
            
            if 'Results' not in data or not data['Results'] or \
               'series' not in data['Results'] or not data['Results']['series'] or \
               'data' not in data['Results']['series'][0] or not data['Results']['series'][0]['data']:
                spinner.fail(f"Failed to fetch {name}: Unexpected data structure or empty series data.")
                print(f"\n{name}: Unexpected data structure or empty series data received.")
                continue

            series_data = data['Results']['series'][0]['data']
            
            if len(series_data) < 2:
                spinner.warn(f"Insufficient data for {name}")
                print(f"\n{name}: No sufficient data available (requires at least 2 data points for comparison).")
                continue
            
            latest_data = series_data[0]
            previous_data = series_data[1]
            
            latest_value = float(latest_data['value'])
            previous_value = float(previous_data['value'])
            year = latest_data['year']
            period = latest_data['periodName']
            
            percentage_change = ((latest_value - previous_value) / previous_value) * 100
            
            spinner.succeed(f'Successfully fetched {name}')
            
            print(f"\n{name}:")
            print(f"  Value: {latest_value}")
            print(f"  Date: {period} {year}")
            print(f"  Month-over-Month Change: {percentage_change:.2f}%")
        
        except requests.exceptions.HTTPError as e:
            spinner.fail(f'Failed to fetch {name}')
            error_message = f"HTTP {e.response.status_code} - {e.response.reason}"
            try: # Try to get more specific error from BLS response
                error_details = e.response.json().get('message')
                if error_details:
                    error_message += f": {', '.join(error_details)}"
            except ValueError: # If response is not JSON or no 'message' field
                pass
            print(f"\nError fetching {name}: {error_message}")
        except Exception as e:
            spinner.fail(f'Failed to process {name}')
            print(f"\nError processing {name}: {e}")
            
    # Removed global spinner stop from a finally block
    
    safe_input("\nPress Enter to continue...")

def bls_menu():
    """Display and handle BLS data menu"""
    while True:
        try:
            print("\n=== BLS Economic Indicators Menu ===")
            print("1. View latest economic indicators")
            print("2. Return to main menu")
            
            choice = safe_input("\nEnter your choice (1-2): ")
            
            if choice == "1":
                display_bls_data()
            elif choice == "2":
                return
            else:
                print("\nInvalid choice. Please enter 1-2.")
        except KeyboardInterrupt:
            exit_gracefully("\n\nProgram interrupted. Goodbye!")
        except EOFError:
            exit_gracefully("\n\nEnd of input. Goodbye!")

def extract_state(matched_address):
    """Extract the state from the matched address"""
    address_parts = matched_address.split(',')
    state = address_parts[-2].strip()  # Assuming state is the second-to-last part
    return state


def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate the distance between two points on a sphere using the Haversine formula"""
    R = 6371  # Radius of the Earth in kilometers
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    distance = R * c
    return distance

def get_nearest_station(address_data):
    """Find the nearest NOAA tide station using metadata API"""
    url = f"https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations.json?format=json"
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
    
    # Extract the state from the address data
    state = extract_state(address_data['matched_address'])
    
    # Manually filter the results to find the stations in the state
    state_stations = [station for station in data['stations'] if station['state'] == state]
    
    # Calculate the distance between each station and the street address
    nearest_station = None
    min_distance = float('inf')
    for station in state_stations:
        station_lat = float(station['lat'])
        station_lon = float(station.get('lon', station.get('lng')))  # Handle both 'lon' and 'lng' keys
        distance = haversine_distance(address_data['lat'], address_data['lon'], station_lat, station_lon)
        if distance < min_distance:
            min_distance = distance
            nearest_station = station['id']
    
    return nearest_station

def get_tide_data(station_id):
    """Fetch tide data from NOAA API for a given station ID"""
    today = datetime.today().strftime("%Y%m%d")
    tomorrow = (datetime.today() + timedelta(days=1)).strftime("%Y%m%d")
    
    url = f"https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
    params = {
        "product": "predictions",
        "application": "NOS.COOPS.TAC.WL",
        "begin_date": f"{today}",
        "end_date": f"{tomorrow}",
        "datum": "MLLW",
        "station": station_id,
        "time_zone": "lst_ldt",
        "units": "english",
        "interval": "hilo",
        "format": "json"
    }
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()

def display_tide_data(tide_data):
    """Display tide information"""
    print("\nTide Information:")
    for prediction in tide_data['predictions']:
        time = datetime.strptime(prediction['t'], "%Y-%m-%d %H:%M")
        tide_type = "High Tide" if prediction['type'] == "H" else "Low Tide"
        formatted_time = time.strftime("%I:%M %p, %A, %B %d, %Y")
        print(f"{formatted_time} - {tide_type}")

def display_station_info(station_info):
    """Display station information"""
    print("\nStation Information:")
    print(f"Station ID: {station_info['stations'][0]['id']}")
    print(f"Station Name: {station_info['stations'][0]['name']}")
    print(f"State: {station_info['stations'][0]['state']}")
    print(f"Latitude: {station_info['stations'][0]['lat']}")
    print(f"Longitude: {station_info['stations'][0]['lng']}")

    # Generate Google Maps URL
    google_maps_url = f"https://www.google.com/maps/@?api=1&map_action=map&center={station_info['stations'][0]['lat']},{station_info['stations'][0]['lng']}&zoom=15"
    print("Google Maps:")
    print(google_maps_url)

def get_station_info(station_id):
    """Fetch station information from NOAA API"""
    url = f"https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/{station_id}.json"
    response = requests.get(url)
    response.raise_for_status()
    return response.json()

def lookup_tides():
    """Handle tide lookup logic"""
    address = safe_input("\nEnter address (street, city, state, zip code): ")
    
    # Get coordinates
    location_data = get_coordinates(address)
    
    if location_data is None:
        print("\nError: Could not find the address. Please check and try again.")
        return
    
    # Display matched address
    print("\nMatched Address:")
    print("-" * 50)
    print(f"Street: {location_data['matched_address'].split(',')[0]}")
    print(f"City: {location_data['matched_address'].split(',')[1].strip()}")
    print(f"State: {location_data['matched_address'].split(',')[2].strip()}")
    print(f"Zip Code: {location_data['matched_address'].split(',')[3].strip()}")
    print(f"Latitude: {location_data['lat']}")
    print(f"Longitude: {location_data['lon']}")
    
    # Generate Google Maps URL
    google_maps_url = f"https://www.google.com/maps/@?api=1&map_action=map&center={location_data['lat']},{location_data['lon']}&zoom=15"
    print(f"\nClick to view matched address on Google Maps: {google_maps_url}")
    
    # Get nearest station
    station_id = get_nearest_station(location_data)
    
    if station_id is None:
        print("\nError: Could not find a nearby tide station.")
        return
    
    # Get station information
    station_info = get_station_info(station_id)
    
    if station_info is None:
        print("\nError: Could not retrieve station information.")
        return
    
    # Display station information
    display_station_info(station_info)
    
    # Get tide data
    try:
        tide_data = get_tide_data(station_id)
        # Save the address to the database since we successfully got tide data
        save_search(address, location_data)
    except requests.exceptions.HTTPError as e:
        print(f"\nError: Failed to retrieve tide data. {e}")
        return
    
    # Display tide data
    display_tide_data(tide_data)

def select_saved_address_for_tides():
    """Handle selecting a saved address for tide lookup"""
    addresses = get_saved_addresses()
    if not addresses:
        print("\nNo saved addresses found.")
        return
    
    print("\nSaved addresses:")
    for i, (address, matched_address, lat, lon, _) in enumerate(addresses, 1):
        print(f"{i}. {matched_address}")
    
    choice = safe_input("\nSelect address number (or 0 to go back): ")
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
            
            # Get nearest station
            station_id = get_nearest_station(location_data)
            
            if station_id is None:
                print("\nError: Could not find a nearby tide station.")
                return
            
            # Get station information
            station_info = get_station_info(station_id)
            
            if station_info is None:
                print("\nError: Could not retrieve station information.")
                return
            
            # Display station information
            display_station_info(station_info)
            
            # Get tide data
            try:
                tide_data = get_tide_data(station_id)
                # Display tide data
                display_tide_data(tide_data)
            except requests.exceptions.HTTPError as e:
                print(f"\nError: Failed to retrieve tide data. {e}")
                return
            
            safe_input("\nPress Enter to continue...")
        else:
            print("\nInvalid selection.")
    except ValueError:
        print("\nPlease enter a valid number.")

def tides_menu():
    """Display and handle tides menu"""
    while True:
        try:
            print("\n=== Tides Menu ===")
            print("1. Enter new address")
            print("2. Select from saved addresses")
            print("3. Return to main menu")
            
            choice = safe_input("\nEnter your choice (1-3): ")
            
            if choice == "1":
                lookup_tides()
            elif choice == "2":
                select_saved_address_for_tides()
            elif choice == "3":
                return
            else:
                print("\nInvalid choice. Please enter 1-3.")
        except KeyboardInterrupt:
            exit_gracefully("\n\nProgram interrupted. Goodbye!")
        except EOFError:
            exit_gracefully("\n\nEnd of input. Goodbye!")

def get_salesforce_credentials():
    """Prompt the user for Salesforce credentials and verify them"""
    global sf_username, sf_password, sf_token, sf_instance

    if sf_instance is not None:
        return sf_instance

    sf_username_env = os.getenv("SALESFORCE_USERNAME")
    sf_password_env = os.getenv("SALESFORCE_PASSWORD")
    sf_token_env = os.getenv("SALESFORCE_SECURITY_TOKEN")

    if sf_username_env and sf_password_env and sf_token_env:
        spinner = Halo('Authenticating with Salesforce using environment variables...')
        spinner.start()
        try:
            sf_instance = Salesforce(username=sf_username_env, password=sf_password_env, security_token=sf_token_env)
            spinner.succeed("Salesforce authentication successful using environment variables.")
            # Store them globally if needed, or just use the instance
            sf_username = sf_username_env
            sf_password = sf_password_env # Not strictly necessary to store if only instance is used
            sf_token = sf_token_env       # Not strictly necessary to store if only instance is used
            return sf_instance
        except SalesforceAuthenticationFailed:
            spinner.fail("Salesforce authentication failed using environment variables.")
            print("Please check your SALESFORCE_USERNAME, SALESFORCE_PASSWORD, and SALESFORCE_SECURITY_TOKEN environment variables.")
            return None
        except Exception as e:
            spinner.fail(f"An unexpected error occurred during Salesforce authentication: {e}")
            return None
        finally:
            if 'spinner' in locals():
                spinner.stop()
    else:
        print("\nSalesforce credentials not found in environment variables.")
        print("Please set SALESFORCE_USERNAME, SALESFORCE_PASSWORD, and SALESFORCE_SECURITY_TOKEN.")
        return None

def query_salesforce_contacts(sf, filter_value):
    query = f"""
    SELECT Account.Name, FirstName, LastName, Title, Email, Phone, Description
    FROM Contact
    WHERE Account.Name LIKE '%{filter_value}%'
    OR FirstName LIKE '%{filter_value}%'
    OR LastName LIKE '%{filter_value}%'
    OR Title LIKE '%{filter_value}%'
    OR Email LIKE '%{filter_value}%'
    """
    
    try:
        contacts = sf.query(query)['records']
    except SalesforceExpiredSession:
        print("\nSalesforce session expired. Please re-enter your credentials.")
        get_salesforce_credentials()
        contacts = sf.query(query)['records']

    if not contacts:
        print("\nNo contacts found.\n")
    else:
        print(f"\nTotal contacts found: {len(contacts)}")
        for contact in contacts:
            print(f"\nAccount Name: {contact['Account']['Name']}")
            print(f"First Name: {contact['FirstName']}")
            print(f"Last Name: {contact['LastName']}")
            print(f"Title: {contact['Title']}")
            print(f"Email: {contact['Email']}")
            print(f"Phone: {contact['Phone']}")
            print(f"Description: {contact['Description']}")
            print("-" * 60)
        print(f"\nTotal contacts found: {len(contacts)}\n")

def salesforce_menu():
    """Display and handle Salesforce menu"""
    try:
        print("\n=== Salesforce Menu ===\n")
        sf = get_salesforce_credentials()

        if sf is None:
            safe_input("\nPress Enter to return to the main menu...")
            return

        while True:
            try:
                print("\n1. Query contacts")
                print("2. Return to main menu")
                
                choice = safe_input("\nEnter your choice (1-2): ")
                
                if choice == "1":
                    filter_value = safe_input("\nEnter filter value: ")
                    query_salesforce_contacts(sf, filter_value)
                elif choice == "2":
                    return
                else:
                    print("\nInvalid choice. Please enter 1-2.")
            except KeyboardInterrupt:
                exit_gracefully("\n\nProgram interrupted. Goodbye!")
            except EOFError:
                exit_gracefully("\n\nEnd of input. Goodbye!")
    except KeyboardInterrupt:
        exit_gracefully("\n\nProgram interrupted. Goodbye!")
    except EOFError:
        exit_gracefully("\n\nEnd of input. Goodbye!")

def get_google_maps_url_for_coordinates(lat, lon):
    """Generate Google Maps URL for the given coordinates"""

    return f"https://www.google.com/maps/place/{lat},{lon}/@{lat},{lon},7z/data=!3m1!1e3"

def earthquakes_menu():
    """Display 5.0 and higher magnitude earthquakes today"""
    # https://earthquake.usgs.gov/fdsnws/event/1/
    # https://earthquake.usgs.gov/fdsnws/event/1/#parameters

    try:
        spinner = Halo('Getting USGS data...')
        spinner.start()
        try:
            # Get the current date one day in the future in YYYY-MM-DD format
            current_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
            # Get the date one day before today
            start_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

            # Insert the current date into the URL
            url = f"https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&starttime={start_date}&endtime={current_date}&minmagnitude=5"
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            
            if not data.get('features'):
                print("\nNo 5.0 earthquakes found today.")
                return
            
            print("\n5.0 earthquakes today:")
            print("-" * 50)
            print(f"\nUSGS URL: {url}\n")
            
            for feature in data['features']:
                properties = feature['properties']
                mag = properties['mag']
                place = properties['place']
                time = datetime.fromtimestamp(properties['time'] / 1000).strftime('%Y-%m-%d %H:%M:%S UTC')
                coordinates = feature['geometry']['coordinates']
                lon, lat = coordinates[0], coordinates[1]
                maps_url = get_google_maps_url_for_coordinates(lat, lon)

                print(f"Magnitude: {mag}")
                print(f"Place: {place}")
                print(f"Time: {time}")
                print(f"Google Maps URL: {maps_url}")
                print("-" * 50)
            
        except Exception as e:
            print(f"\nError getting earthquake data: {e}")
        finally:
            spinner.stop()
        
        try:
            safe_input("\nPress Enter to continue...")
        except (KeyboardInterrupt, EOFError):
            exit_gracefully("\n\nProgram interrupted. Goodbye!")
    
    except (KeyboardInterrupt, EOFError):
        exit_gracefully("\n\nProgram interrupted. Goodbye!")

def get_fred_data(series_id, api_key):
    """Fetch data from FRED API for a given series ID."""
    # Request the last 2 observations, sorted in descending order by date
    url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={api_key}&file_type=json&sort_order=desc&limit=2"
    response = requests.get(url)
    response.raise_for_status()
    return response.json()

def display_fred_indicators():
    """Display economic indicators from FRED API."""
    api_key = os.getenv("FRED_API_KEY")
    if not api_key:
        print("\nError: FRED_API_KEY environment variable not set.")
        print("Please set it to your FRED API key to use this feature.")
        print("You can obtain a key from: https://fred.stlouisfed.org/docs/api/api_key.html")
        safe_input("\nPress Enter to continue...")
        return

    # Removed global spinner initialization
    
    series_ids = {
        "Effective Federal Funds Rate": "FEDFUNDS",
        "10-Year Treasury Constant Maturity Rate": "DGS10",
        "M2 Money Stock (Billions of $)": "M2SL",
        "Industrial Production Index (2017=100)": "INDPRO",
        "Gross Domestic Product (Billions of $)": "GDP",
        "CPI All Urban Consumers (Index 1982-84=100)": "CPIAUCSL",
        "Civilian Unemployment Rate (%)": "UNRATE",
        "30-Year Fixed Rate Mortgage Average (%)": "MORTGAGE30US",
        "Housing Starts (Thousands of Units)": "HOUST",
        "Consumer Sentiment (U. Michigan)": "UMCSENT",
        "Initial Claims (Weekly)": "ICSA",
        "S&P/Case-Shiller U.S. Home Price Index": "CSUSHPINSA"
    }
    
    fetched_results = []

    print("\n--- Federal Reserve Economic Indicators ---")

    for name, series_id in series_ids.items():
        spinner = Halo(text=f'Fetching {name}...', spinner='dots')
        spinner.start()
        try:
            data = get_fred_data(series_id, api_key) # Network call
            observations = data.get('observations', [])
            
            if len(observations) < 2:
                spinner.warn(f"Insufficient data for {name}")
                fetched_results.append({'name': name, 'error': "Not enough data available (requires at least 2 observations)."})
                continue
            
            latest_data = observations[0]
            previous_data = observations[1]
            
            if latest_data['value'] == '.' or previous_data['value'] == '.':
                spinner.warn(f"Data point missing for {name}")
                fetched_results.append({
                    'name': name, 
                    'error': "Data point missing for latest or previous period.",
                    'latest_date': latest_data['date'],
                    'latest_value_raw': latest_data['value'],
                    'previous_date': previous_data['date'],
                    'previous_value_raw': previous_data['value']
                })
                continue

            latest_value = float(latest_data['value'])
            previous_value = float(previous_data['value'])
            change = latest_value - previous_value
            
            spinner.succeed(f"Successfully fetched {name}")
            result_item = {
                'name': name,
                'latest_date': latest_data['date'],
                'latest_value': latest_value,
                'previous_date': previous_data['date'],
                'previous_value': previous_value,
                'change': change,
                'is_percentage_change': series_id in ["M2SL", "INDPRO", "GDP", "CPIAUCSL", "HOUST", "CSUSHPINSA"]
            }
            fetched_results.append(result_item)

        except requests.exceptions.HTTPError as item_e:
            error_detail_msg = str(item_e)
            if item_e.response is not None:
                error_detail_msg = f"HTTP {item_e.response.status_code} - {item_e.response.reason}"
                if item_e.response.status_code == 400:
                    try:
                        error_detail = item_e.response.json()
                        error_detail_msg += f": {error_detail.get('error_message', 'No additional details.')}"
                    except json.JSONDecodeError:
                        pass # Keep original error_detail_msg
            spinner.fail(f"Failed to fetch {name}")
            fetched_results.append({'name': name, 'error': f"Failed to fetch: {error_detail_msg}"})
        except Exception as item_e:
            spinner.fail(f"Failed to process {name}")
            fetched_results.append({'name': name, 'error': f"An unexpected error occurred: {item_e}"})

    # Print results after all spinners are done
    if not fetched_results:
        print("No indicators to display or all attempts failed.")
    else:
        for result in fetched_results:
            print(f"\n{result['name']}:")
            if 'error' in result:
                if result['error'] == "Data point missing for latest or previous period.":
                     print(f"  {result['error']}")
                     print(f"  Latest ({result.get('latest_date','N/A')}): {result.get('latest_value_raw','N/A')}")
                     print(f"  Previous ({result.get('previous_date','N/A')}): {result.get('previous_value_raw','N/A')}")
                else:
                    print(f"  Error: {result['error']}")
                continue

            print(f"  Latest Value ({result['latest_date']}): {result['latest_value']}")
            
            if result['is_percentage_change']:
                if result['previous_value'] != 0:
                    percentage_change = (result['change'] / result['previous_value']) * 100
                    print(f"  Change from Previous ({result['previous_date']}): {percentage_change:+.2f}% (from {result['previous_value']})")
                else:
                    print(f"  Change from Previous ({result['previous_date']}): N/A (previous value was 0)")
            else:
                print(f"  Change from Previous ({result['previous_date']}): {result['change']:+.2f} (from {result['previous_value']})")
            
    safe_input("\nPress Enter to continue...")

def fred_menu():
    """Display and handle FRED data menu"""
    while True:
        try:
            print("\n=== US Federal Reserve Indicators Menu ===")
            print("1. View latest Federal Reserve indicators")
            print("2. Return to main menu")
            
            choice = safe_input("\nEnter your choice (1-2): ")
            
            if choice == "1":
                display_fred_indicators()
            elif choice == "2":
                return
            else:
                print("\nInvalid choice. Please enter 1-2.")
        except KeyboardInterrupt:
            exit_gracefully("\n\nProgram interrupted. Goodbye!")
        except EOFError:
            exit_gracefully("\n\nEnd of input. Goodbye!")

def main_menu():
    """Display and handle main menu"""
    init_db()  # Ensure database exists
    while True:
        try:
            print("\n=== Multi-Service CLI Tool ===")
            print("1. Weather Lookup")
            print("2. Scores")
            print("3. News")
            print("4. BLS Economic Indicators")
            print("5. US Federal Reserve Indicators") # Moved FRED
            print("6. Tides") # Renumbered
            print("7. Salesforce") # Renumbered
            print("8. Earthquakes") # Renumbered
            print("9. Quit")
            
            choice = safe_input("\nEnter your choice (1-9): ")
            
            if choice == "1":
                weather_menu()
            elif choice == "2":
                scores_menu()
            elif choice == "3":
                news_menu()
            elif choice == "4":
                bls_menu()
            elif choice == "5": # Adjusted choice for FRED
                fred_menu()
            elif choice == "6": # Adjusted choice
                tides_menu()
            elif choice == "7": # Adjusted choice
                salesforce_menu()
            elif choice == "8": # Adjusted choice
                earthquakes_menu()
            elif choice == "9":
                exit_gracefully()
            else:
                print("\nInvalid choice. Please enter 1-9.")
        except KeyboardInterrupt:
            exit_gracefully("\n\nProgram interrupted. Goodbye!")
        except EOFError:
            exit_gracefully("\n\nEnd of input. Goodbye!")

def exit_gracefully(message="\nGoodbye!"):
    """Exit the program gracefully with a message"""
    print(message)
    sys.exit(0)

def safe_input(prompt):
    """Safely handle user input with keyboard interrupt and EOF handling"""
    try:
        return input(prompt)
    except (KeyboardInterrupt, EOFError):
        exit_gracefully("\n\nProgram interrupted. Goodbye!")

if __name__ == "__main__":
    try:
        # Notify users if debug mode is active
        if DEBUG_MODE:
            print("\n*** Debug Mode Active - Additional diagnostic information will be displayed ***")
        
        main_menu()
    except KeyboardInterrupt:  # Handle Ctrl+C
        exit_gracefully("\n\nProgram interrupted. Goodbye!")
    except EOFError:  # Handle Ctrl+D
        exit_gracefully("\n\nEnd of input. Goodbye!")
