import requests
import sys
import urllib.parse
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
    conn = sqlite3.connect('weather_history.db', detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
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
    conn = sqlite3.connect('weather_history.db', detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
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
    conn = sqlite3.connect('weather_history.db', detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
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
    spinner = Halo('Fetching economic indicators...')
    spinner.start()
    
    try:
        # Define the series IDs for the required economic indicators
        series_ids = {
            "CPI": "CUSR0000SA0",
            "CPI Less Food and Energy": "CUSR0000SA0L1E",
            "PPI": "PCUOMFG--OMFG--",
            "Nonfarm Payroll": "CES0000000001",
            "Unemployment Rate": "LNS14000000"
        }
        
        for name, series_id in series_ids.items():
            data = get_bls_data(series_id)
            series_data = data['Results']['series'][0]['data']
            
            if len(series_data) < 2:
                print(f"\n{name}: No sufficient data available.")
                continue
            
            # Extract the latest and previous data points
            latest_data = series_data[0]
            previous_data = series_data[1]
            
            latest_value = float(latest_data['value'])
            previous_value = float(previous_data['value'])
            year = latest_data['year']
            period = latest_data['periodName']
            
            # Calculate percentage change
            percentage_change = ((latest_value - previous_value) / previous_value) * 100
            
            print(f"\n{name}:")
            print(f"  Value: {latest_value}")
            print(f"  Date: {period} {year}")
            print(f"  Month-over-Month Change: {percentage_change:.2f}%")
        
    except Exception as e:
        print(f"\nError fetching BLS data: {e}")
    finally:
        spinner.stop()
    
    input("\nPress Enter to continue...")

def bls_menu():
    """Display and handle BLS data menu"""
    while True:
        print("\n=== BLS Economic Indicators Menu ===")
        print("1. View latest economic indicators")
        print("2. Return to main menu")
        
        choice = input("\nEnter your choice (1-2): ")
        
        if choice == "1":
            display_bls_data()
        elif choice == "2":
            return
        else:
            print("\nInvalid choice. Please enter 1-2.")

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
    address = input("\nEnter address (street, city, state, zip code): ")
    
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
            
            input("\nPress Enter to continue...")
        else:
            print("\nInvalid selection.")
    except ValueError:
        print("\nPlease enter a valid number.")

def tides_menu():
    """Display and handle tides menu"""
    while True:
        print("\n=== Tides Menu ===")
        print("1. Enter new address")
        print("2. Select from saved addresses")
        print("3. Return to main menu")
        
        choice = input("\nEnter your choice (1-3): ")
        
        if choice == "1":
            lookup_tides()
        elif choice == "2":
            select_saved_address_for_tides()
        elif choice == "3":
            return
        else:
            print("\nInvalid choice. Please enter 1-3.")

def get_salesforce_credentials():
    """Prompt the user for Salesforce credentials and verify them"""
    global sf_username, sf_password, sf_token, sf_instance

    if sf_instance is not None:
            return sf_instance

    while True:
        sf_username = input("Enter Salesforce username: ")
        sf_password = input("Enter Salesforce password: ")
        sf_token = input("Enter Salesforce security token: ")
        
        try:
            sf_instance = Salesforce(username=sf_username, password=sf_password, security_token=sf_token)
            print("\nSalesforce credentials verified successfully.\n")
            return sf_instance
        except SalesforceAuthenticationFailed:
            print("\nInvalid Salesforce credentials. Please try again.\n")

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
    print("\n=== Salesforce Menu ===\n")
    sf = get_salesforce_credentials()
    while True:
        print("1. Query contacts")
        print("2. Return to main menu")
        
        choice = input("\nEnter your choice (1-2): ")
        
        if choice == "1":
            filter_value = input("\nEnter filter value: ")
            query_salesforce_contacts(sf, filter_value)
        elif choice == "2":
            return
        else:
            print("\nInvalid choice. Please enter 1-2.")

def get_google_maps_url_for_coordinates(lat, lon):
    """Generate Google Maps URL for the given coordinates"""

    return f"https://www.google.com/maps/place/{lat},{lon}/@{lat},{lon},7z/data=!3m1!1e3"

def earthquakes_menu():
    """Display 5.0 and higher magnitude earthquakes today"""
    # https://earthquake.usgs.gov/fdsnws/event/1/
    # https://earthquake.usgs.gov/fdsnws/event/1/#parameters


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
    
    input("\nPress Enter to continue...")

def main_menu():
    """Display and handle main menu"""
    init_db()  # Ensure database exists
    while True:
        print("\n=== Multi-Service CLI Tool ===")
        print("1. Weather Lookup")
        print("2. NFL Scores")
        print("3. News")
        print("4. BLS Economic Indicators")
        print("5. Tides")
        print("6. Salesforce")
        print("7. Earthquakes")
        print("8. Quit")
        
        choice = input("\nEnter your choice (1-6): ")
        
        if choice == "1":
            weather_menu()
        elif choice == "2":
            nfl_menu()
        elif choice == "3":
            news_menu()
        elif choice == "4":
            bls_menu()
        elif choice == "5":
            tides_menu()
        elif choice == "6":
            salesforce_menu()
        elif choice == "7":
            earthquakes_menu()
        elif choice == "8":
            print("\nGoodbye!")
            sys.exit(0)
        else:
            print("\nInvalid choice. Please enter 1-6.")

if __name__ == "__main__":
    main_menu()
