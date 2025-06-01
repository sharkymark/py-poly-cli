# Multi-Service CLI Tool

A command-line interface tool that provides various web service integrations including weather lookup, NFL scores, news aggregation, economic indicators, tide information, and earthquake data.

## Features

- Weather lookup by address
  - Converts addresses to coordinates using Census Geocoding API
  - Fetches detailed weather data from National Weather Service API
  - Stores recent lookups in local SQLite database (`history.db`)
  - Generates Google Maps links for looked-up addresses

- Sports Scores
  - Real-time game scores from ESPN API for multiple leagues:
    - NFL (National Football League)
    - MLB (Major League Baseball)
    - NHL (National Hockey League)
    - NBA (National Basketball Association)
    - MLS (Major League Soccer)
    - NCAA College Football
  - Shows upcoming, in-progress, and completed games
  - Displays current game period and score for live games

- News Aggregation
  - Fetches latest news articles using Google News
  - Filter articles by specific domains (e.g., wsj.com)
  - Displays article titles, publication dates, and URLs
  - Limited to 5 most recent articles per query
  - Includes default news sites (wsj.com, washingtonpost.com, nytimes.com, apnews.com, whitehouse.gov)
  - Saves user-entered domains to the database for future use
  - Organizes news sources into "Default News Sites" and "Saved News Sites" categories

- BLS Economic Indicators
  - Retrieves key economic indicators from the BLS API
  - Includes CPI, CPI less food and energy, PPI, Nonfarm payroll, and Unemployment rate
  - Displays data in a format preferred by financial analysts, including month-over-month changes and actual values

- Tide Information
  - Converts address to coordinates using Census Geocoding API
  - Finds the nearest NOAA tide station and displays its information (name, ID, coordinates)
  - Generates a Google Maps link for the tide station
  - Retrieves tide predictions from NOAA API
  - Displays high and low tide times and types

- Querying Salesforce contacts
  - Checks for `SALESFORCE_USERNAME`, `SALESFORCE_PASSWORD`, and `SALESFORCE_SECURITY_TOKEN` environment variables.
  - Attempts authentication using environment variables if set.
  - If environment variables are not set or authentication fails, instructs the user to set/check them.
  - Retrieves contact records based on filter criteria.

- Earthquake Information
  - Retrieves last 24 hours 5.0 earthquake data from the USGS Earthquake API
  - Displays earthquake magnitude, location, and time
  - Filters results by minimum magnitude and time range

- US Federal Reserve (FRED) Indicators
  - Checks for `FRED_API_KEY` environment variable.
  - Fetches and displays key economic indicators from the FRED API if the key is set.
  - Indicators include: Effective Federal Funds Rate, 10-Year Treasury Rate, M2 Money Stock, Industrial Production, GDP, CPI, Unemployment Rate, Mortgage Rates, Housing Starts, Consumer Sentiment, Initial Claims, and Home Price Index.
  - Shows the latest value, its date, and the change from the previous observation.

## Installation

This project uses DevContainers for development. To get started:

1. Install Docker and VS Code
2. Open the project in VS Code
3. Install the "Remote - Containers" extension
4. Click "Reopen in Container" when prompted

The container will automatically install all dependencies and start the application.

Alternatively, you can set up manually:

```bash
# Clone the repository
git clone <repository-url>
cd py-poly-cli

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

Run the application:

```bash
python3 poly_cli.py
```

If using a dev container, the application is started automatically.

Navigate through the menus to:
1. Look up weather for a new address or select from recent lookups
2. View live sports scores for various leagues (NFL, MLB, NHL, NBA, MLS, College Football)
3. Browse latest news articles from specific domains
   - Enter a new domain or select from default/saved news sites
   - Default sites include: wsj.com, washingtonpost.com, nytimes.com, apnews.com, whitehouse.gov
4. View latest economic indicators from the BLS
5. Look up tide information by address
6. Query Salesforce contacts
7. View recent earthquake information
8. View US Federal Reserve (FRED) economic indicators
9. Exit the application

The application features graceful exit handling with Ctrl+C and Ctrl+D, allowing you to exit safely from any menu.

## Environment Variables

To use the Salesforce and Federal Reserve APIs, you will need to set the following environment variables:

*   `SALESFORCE_USERNAME`: Your Salesforce username.
*   `SALESFORCE_PASSWORD`: Your Salesforce password.
*   `SALESFORCE_SECURITY_TOKEN`: Your Salesforce security token.
*   `FRED_API_KEY`: Your FRED API key for accessing economic indicators.

When using the provided Dev Container, these variables can be configured in your local environment and will be passed into the container. Refer to the `.devcontainer/devcontainer.json` file for more details on how these are sourced.

## Resources

### APIs Used
- [Census Geocoding Services](https://geocoding.geo.census.gov/geocoder/Geocoding_Services_API.html) - Convert addresses to coordinates
- [National Weather Service API](https://www.weather.gov/documentation/services-web-api) - Weather data and forecasts
- [ESPN API](https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard) - NFL scores and game information
- [Google News](https://news.google.com/) - News article aggregation via GNews library
- [BLS API](https://www.bls.gov/developers/) - Economic indicators data
- [NOAA Tides and Currents API](https://tidesandcurrents.noaa.gov/api/) - Tide predictions
- [simple_salesforce](https://pypi.org/project/simple-salesforce/) - A basic Salesforce.com REST API client for Python.
- [GitHub Repository](https://github.com/simple-salesforce/simple-salesforce)
- [USGS Earthquake API](https://earthquake.usgs.gov/fdsnws/event/1/) - Recent earthquake data
- [FRED API (Federal Reserve Economic Data)](https://fred.stlouisfed.org/docs/api/fred/) - US economic indicators

### Data Storage
- SQLite database (`history.db`) stores:
  - Weather search history (addresses, coordinates)
  - News site URLs (both default and user-saved)

### Development
- [DevContainer Specification](https://containers.dev/implementors/spec/) - Learn about DevContainer configuration

## Requirements
- Python 3.11+
- Docker (for development container)
- Required Python packages (included in requirements.txt):
  - requests: For API calls
  - halo: For terminal spinners
  - python-dateutil: For date parsing and formatting
  - gnews: For Google News integration
  - simple_salesforce: For Salesforce API interaction
