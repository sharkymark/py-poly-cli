# Multi-Service CLI Tool

A command-line interface tool that provides various web service integrations. Currently features weather lookup functionality using the U.S. Census Geocoding API and NOAA's National Weather Service API.

## Features

- Weather lookup by address
  - Converts addresses to coordinates using Census Geocoding API
  - Fetches detailed weather data from National Weather Service API
  - Stores recent lookups in local SQLite database
  - Generates Google Maps links for looked-up addresses

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
1. Look up weather for a new address
2. Select from recently looked-up addresses
3. View current conditions and forecasts

## Resources

### APIs Used
- [Census Geocoding Services](https://geocoding.geo.census.gov/geocoder/Geocoding_Services_API.html) - Convert addresses to coordinates
- [National Weather Service API](https://www.weather.gov/documentation/services-web-api) - Weather data and forecasts

### Development
- [DevContainer Specification](https://containers.dev/implementors/spec/) - Learn about DevContainer configuration

## Requirements
- Python 3.11+
- Docker (for development container)
- Required Python packages listed in requirements.txt