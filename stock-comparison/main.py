import yfinance as yf
import pandas as pd
import numpy as np
import datetime as dt

# Define the stock and cryptocurrency symbols
symbols_stocks = ['QQQ', 'SPY', 'TSLA', 'META', 'ARKK', 'AAPL', 'AMZN', 'GOOGL', 'MSFT', 'NVDA']
symbols_crypto = ['BTC-USD', 'ETH-USD']
symbols = symbols_stocks + symbols_crypto

# Fetch historical data for the past decade
today = dt.datetime.now()
start_date = today - pd.DateOffset(years=10)

data = {}
for symbol in symbols:
    stock = yf.Ticker(symbol)
    data[symbol] = stock.history(start=start_date, end=today)['Close']

# Combine data into a DataFrame
combined_data = pd.DataFrame(data)
combined_data = combined_data.ffill()

# Replace cumulative_returns with the first valid value for each symbol
initial_values = combined_data.apply(lambda col: col.loc[col.first_valid_index()], axis=0)
cumulative_returns = (combined_data / initial_values - 1) * 100

# Calculate annualized volatility
daily_returns = combined_data.pct_change()
annualized_volatility = daily_returns.std() * np.sqrt(252)

# Project future trends for the next 10 years
future_trends = {}
for symbol in symbols:
    x_numeric = np.arange(len(cumulative_returns))
    y_data = cumulative_returns[symbol].dropna().values
    if len(y_data) > 1:
        trend_coeffs = np.polyfit(x_numeric[:len(y_data)], y_data, 1)
        future_trends[symbol] = trend_coeffs[0] * (len(x_numeric) + 2520) + trend_coeffs[1]  # Project 10 years
    else:
        future_trends[symbol] = np.nan

# Create a summary table
results = pd.DataFrame({
    'Total Return (%)': cumulative_returns.iloc[-1],
    'Annualized Volatility (%)': annualized_volatility * 100,
    'Projected 10-Year Trend (%)': future_trends
})

# Display the results table
print("\nStock and Cryptocurrency Performance Overview:")
print(results.sort_values(by='Total Return (%)', ascending=False))
