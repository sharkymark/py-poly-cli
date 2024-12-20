# Multi-Service CLI Tool

A command-line interface tool that provides various web service integrations including weather lookup, NFL scores, news aggregation, and economic indicators.

## Features

- Weather lookup by address
  - Converts addresses to coordinates using Census Geocoding API
  - Fetches detailed weather data from National Weather Service API
  - Stores recent lookups in local SQLite database
  - Generates Google Maps links for looked-up addresses

- NFL Scores
  - Real-time game scores from ESPN API
  - Shows upcoming, in-progress, and completed games
  - Displays current game period and score for live games

- News Aggregation
  - Fetches latest news articles using Google News
  - Filter articles by specific domains (e.g., wsj.com)
  - Displays article titles, publication dates, and URLs
  - Limited to 5 most recent articles per query

- BLS Economic Indicators
  - Retrieves key economic indicators from the BLS API
  - Includes CPI, CPI less food and energy, PPI, PCE, Nonfarm payroll, Unemployment rate, Initial claims for unemployment insurance, and Retail sales
  - Displays data in a format preferred by financial analysts, including month-over-month changes and actual values

## Installation

This project uses DevContainers for development. To get started:

1. Install Docker and VS Code
2. Open the project in VS Code
3. Install the "Remote - Containers" extension
4. Click "Reopen in Container" when prompted

The container will automatically install all dependencies and start the application.

## Usage

Run the application:

```bash
python3 poly_cli.py
```

If using a dev container, the application is started automatically.

Navigate through the menus to:
1. Look up weather for a new address or select from recent lookups
2. View live NFL scores and game information
3. Browse latest news articles from specific domains
4. View latest economic indicators from the BLS
5. Exit the application

## Resources

### APIs Used
- [Census Geocoding Services](https://geocoding.geo.census.gov/geocoder/Geocoding_Services_API.html) - Convert addresses to coordinates
- [National Weather Service API](https://www.weather.gov/documentation/services-web-api) - Weather data and forecasts
- [ESPN API](https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard) - NFL scores and game information
- [Google News](https://news.google.com/) - News article aggregation
- [BLS API](https://www.bls.gov/developers/) - Economic indicators data

### Development
- [DevContainer Specification](https://containers.dev/implementors/spec/) - Learn about DevContainer configuration

## Requirements
- Python 3.11+
- Docker (for development container)
- Required Python packages listed in requirements.txt