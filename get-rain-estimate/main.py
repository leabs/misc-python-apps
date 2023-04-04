import requests
from datetime import datetime

# Paste your API key here
API_KEY = ""
CITY_NAME = 'Syracuse'
STATE_CODE = 'NY'
COUNTRY_CODE = 'US'
LOCATION = f"{CITY_NAME},{STATE_CODE},{COUNTRY_CODE}"
BASE_URL = f"http://api.openweathermap.org/data/2.5/forecast?q={LOCATION}&appid={API_KEY}&units=imperial"


def get_weather_data():
    response = requests.get(BASE_URL)
    return response.json()


def main():
    weather_data = get_weather_data()
    # Create array of days with rain in the forecast
    days_with_rain = []
    for forecast in weather_data['list']:
        if forecast['weather'][0]['main'] == 'Rain':
            # Get the date of the forecast
            forecast_date = datetime.fromtimestamp(forecast['dt'])
            # Get total rainfall estimate for the entire day
            rain = forecast['rain']['3h']
            # Check if the date is already in the array
            if forecast_date.date() not in days_with_rain:
                days_with_rain.append(forecast_date.date())

    # Convert days_with_rain to day and date (ex. Tuesday the 4th)
    days_with_rain = [day.strftime("%A %d") for day in days_with_rain]

    # Print the days along with the {rain} inches of rain
    print(f"Expect rain on: {days_with_rain}")


if __name__ == "__main__":
    main()
