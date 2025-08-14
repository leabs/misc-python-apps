import requests
import pandas as pd
import numpy as np
from typing import Optional

MAX_BASE = 1500.0
MID_BASE = 750.0

def calculate_investment(power_law_level: float, annual_budget: float, frequency: str) -> int:
    """
    Returns an integer recommended investment per period based on the power law level.
    frequency must be one of: 'monthly', 'weekly', 'daily'
    """
    # determine base_investment according to original piecewise logic
    if power_law_level <= 0:
        base_investment = MAX_BASE
    elif power_law_level <= 100:
        base_investment = MAX_BASE - (power_law_level * (MAX_BASE - MID_BASE) / 100.0)
    elif power_law_level <= 200:
        base_investment = MID_BASE - ((power_law_level - 100.0) * (MID_BASE - 0.0) / 100.0)
    else:
        base_investment = 0.0

    periods_per_year = {"monthly": 12, "weekly": 52, "daily": 365}
    if frequency not in periods_per_year:
        raise ValueError(f"Invalid frequency '{frequency}'. Choose from {list(periods_per_year.keys())}.")

    periods = periods_per_year[frequency]
    adjusted_investment = (annual_budget / periods) * (base_investment / MAX_BASE)
    return int(round(adjusted_investment))

def fetch_current_price(timeout: float = 10.0) -> Optional[float]:
    """Fetch latest BTC price in USD from CoinGecko. Returns float or None."""
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        price = data.get("bitcoin", {}).get("usd")
        if price is None:
            raise ValueError("Unexpected response structure from CoinGecko.")
        return float(price)
    except Exception as e:
        print(f"[fetch_current_price] Error: {e}")
        return None

def calculate_power_law_level(timeout: float = 10.0) -> Optional[float]:
    """
    Fits a log-time / log-price line to blockchain.info market-price, computes
    where current price sits between model bottom and top. Returns a percentage.
    """
    try:
        url = "https://api.blockchain.info/charts/market-price?timespan=all&format=json&cors=true"
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        data = response.json()

        values = data.get("values")
        if not values:
            raise ValueError("No historical values returned from blockchain.info")

        df = pd.DataFrame(values)
        if 'x' not in df.columns or 'y' not in df.columns:
            raise ValueError("Unexpected data format from blockchain.info")

        df = df.rename(columns={'x': 'timestamp_s', 'y': 'price'})
        df['timestamp'] = pd.to_datetime(df['timestamp_s'], unit='s')
        df = df[['timestamp', 'price']].dropna()
        df = df.sort_values('timestamp')

        if len(df) < 2:
            raise ValueError("Not enough historical points for regression.")

        # compute days since start; replace zero with small positive to avoid log(0)
        df['days_since_start'] = (df['timestamp'] - df['timestamp'].min()).dt.total_seconds() / (60 * 60 * 24)
        df.loc[df['days_since_start'] <= 0, 'days_since_start'] = 1e-10

        # replace non-positive prices just in case
        df.loc[df['price'] <= 0, 'price'] = 1e-10

        df['log_time'] = np.log(df['days_since_start'].astype(float))
        df['log_price'] = np.log(df['price'].astype(float))

        # remove any non-finite rows
        df = df[np.isfinite(df['log_time']) & np.isfinite(df['log_price'])]
        if len(df) < 2:
            raise ValueError("Not enough valid log points for regression.")

        coeffs = np.polyfit(df['log_time'], df['log_price'], 1)
        regression = np.poly1d(coeffs)

        df['central_price'] = np.exp(regression(df['log_time']))
        bottom_price = float(df['central_price'].min())
        top_price = float(df['central_price'].max())

        current_price = fetch_current_price(timeout=timeout)
        if current_price is None:
            raise ValueError("Current price could not be fetched.")

        # Protect against degenerate case where top_price == bottom_price
        if top_price <= 0 or bottom_price <= 0:
            raise ValueError("Invalid modelled prices (non-positive).")

        denom = np.log(top_price / bottom_price)
        if np.isclose(denom, 0.0):
            # If the model produced a flat central_price (unlikely), map to 100% when equal to that price
            power_law_level = 100.0 * (np.log(current_price / bottom_price) / (denom + 1e-12))
        else:
            power_law_level = 100.0 * (np.log(current_price / bottom_price) / denom)

        # Optional: clamp to a reasonable range so downstream logic is stable
        # e.g., allow some negative values but prevent huge outliers
        power_law_level = float(np.clip(power_law_level, -200.0, 400.0))

        return power_law_level

    except Exception as e:
        print(f"[calculate_power_law_level] Error: {e}")
        return None

def main():
    current_price = fetch_current_price()
    if current_price is not None:
        print(f"The current price of Bitcoin is: ${current_price:,.2f}")

    power_law_level = calculate_power_law_level()
    if power_law_level is None:
        print("Could not calculate power law level. Exiting.")
        return

    print(f"The current power law level is: {power_law_level:.2f}%")

    # get user input (example: validate positive number)
    while True:
        try:
            annual_investment = float(input("How much would you like to invest a year? "))
            if annual_investment <= 0:
                print("Please enter a positive number.")
                continue
            break
        except ValueError:
            print("Please enter a valid number.")

    annual_investment = round(annual_investment)

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
    adjusted = calculate_investment(power_law_level, annual_investment, frequency)

    print(f"You chose to invest ${annual_investment} per year.")
    print(f"You chose a {frequency.capitalize()} investment frequency.")
    print(f"Based on the power law level, your adjusted investment per period is: ${adjusted}.")

if __name__ == "__main__":
    main()
