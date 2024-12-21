import requests
import pandas as pd
import numpy as np

def calculate_investment(power_law_level, annual_budget, frequency):
    if power_law_level <= 0:
        base_investment = 1500  # Maximum investment when the price is near the bottom
    elif power_law_level <= 100:
        base_investment = 1500 - (power_law_level * (1500 - 750) / 100)
    elif power_law_level <= 200:
        base_investment = 750 - ((power_law_level - 100) * (750 - 0) / 100)
    else:
        base_investment = 0

    periods_per_year = {"monthly": 12, "weekly": 52, "daily": 365}
    periods = periods_per_year.get(frequency, 12)
    adjusted_investment = (annual_budget / periods) * (base_investment / 1500)
    return round(adjusted_investment)

def fetch_current_price():
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        return data['bitcoin']['usd']
    except Exception as e:
        print(f"Error fetching current price: {e}")
        return None

def calculate_power_law_level():
    try:
        url = "https://api.blockchain.info/charts/market-price?timespan=all&format=json&cors=true"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        values = data['values']
        df = pd.DataFrame(values)
        df['timestamp'] = pd.to_datetime(df['x'], unit='s')
        df['price'] = df['y']
        df = df[['timestamp', 'price']]

        df['days_since_start'] = (df['timestamp'] - df['timestamp'].min()).dt.total_seconds() / (60 * 60 * 24)
        df['days_since_start'] = df['days_since_start'].replace(0, 1e-10)

        df['price'] = df['price'].replace(0, 1e-10)
        df['log_time'] = np.log(df['days_since_start'])
        df['log_price'] = np.log(df['price'])

        coefficients = np.polyfit(df['log_time'], df['log_price'], 1)
        regression_line = np.poly1d(coefficients)

        df['central_price'] = np.exp(regression_line(df['log_time']))
        bottom_price = df['central_price'].min()
        top_price = df['central_price'].max()

        current_price = fetch_current_price()
        if current_price is None:
            raise ValueError("Current price could not be fetched.")

        power_law_level = 100 * (
            np.log(current_price / bottom_price) / 
            np.log(top_price / bottom_price)
        )

        return power_law_level
    except Exception as e:
        print(f"Error in power law level calculation: {e}")
        return None

def main():
    # Fetch and print the current Bitcoin price
    current_price = fetch_current_price()
    if current_price is not None:
        print(f"The current price of Bitcoin is: ${current_price}")

    # Calculate and print the power law level
    power_law_level = calculate_power_law_level()
    if power_law_level is not None:
        print(f"The current power law level is: {power_law_level}")
    else:
        print("Could not calculate power law level. Exiting.")
        return

    # Ask the user for annual investment amount
    while True:
        try:
            annual_investment = float(input("How much would you like to invest a year? "))
            if annual_investment <= 0:
                print("Please enter a positive number.")
                continue
            break
        except ValueError:
            print("Please enter a valid number.")

    # Round the annual investment to the nearest whole number
    annual_investment = round(annual_investment)

    # Ask the user for the investment frequency option
    print("Select an option for investment frequency:")
    print("1. Monthly")
    print("2. Weekly")
    print("3. Daily")

    while True:
        try:
            frequency_option = int(input("Enter your choice (1, 2, or 3): "))
            if frequency_option not in [1, 2, 3]:
                print("Please select a valid option (1, 2, or 3).")
                continue
            break
        except ValueError:
            print("Please enter a valid number (1, 2, or 3).")

    frequency = {1: "monthly", 2: "weekly", 3: "daily"}[frequency_option]

    # Calculate adjusted investment
    adjusted_investment = calculate_investment(power_law_level, annual_investment, frequency)

    # Output the results
    print(f"You chose to invest ${annual_investment} per year.")
    print(f"You chose a {frequency.capitalize()} investment frequency.")
    print(f"Based on the power law level, your adjusted investment per period is: ${adjusted_investment}.")

if __name__ == "__main__":
    main()
