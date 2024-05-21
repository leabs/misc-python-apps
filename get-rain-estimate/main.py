import requests
from datetime import datetime
import os
from dotenv import load_dotenv
from collections import defaultdict

# Load the environment variables
load_dotenv()

# Get your API key from environment
API_KEY = os.getenv("OPENWEATHER_API_KEY")
CITY_NAME = 'Syracuse'
STATE_CODE = 'NY'
COUNTRY_CODE = 'US'
LOCATION = f"{CITY_NAME},{STATE_CODE},{COUNTRY_CODE}"
BASE_URL = f"http://api.openweathermap.org/data/2.5/forecast?q={LOCATION}&appid={API_KEY}&units=imperial"

# Get the weather data
response = requests.get(BASE_URL)

# Check response status
if response.status_code != 200:
    print(f"Error: {response.status_code} - {response.reason}")
else:
    weather_data = response.json()

    # Print daily rain estimate
    if 'list' in weather_data:
        daily_rain_estimate = defaultdict(float)
        
        for item in weather_data['list']:
            date = datetime.fromtimestamp(item['dt']).strftime('%Y-%m-%d')
            rain_info = item.get('rain', {})
            rain_mm = rain_info.get('3h', 0)  # Get the rain volume in the last 3 hours
            rain_in = rain_mm * 0.0393701  # Convert mm to inches
            daily_rain_estimate[date] += rain_in
        
        total_rain_estimate = 0
        for date, rain in daily_rain_estimate.items():
            print(f"Date: {date}, Rain: {rain:.2f} inches")
            total_rain_estimate += rain

        print(f"Total rain estimate for the next 5 days: {total_rain_estimate:.2f} inches")
    else:
        print("Error fetching the weather data. Please check your API key and location.")