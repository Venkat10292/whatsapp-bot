import os
import requests
import pandas as pd

ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")

BASE_URL = "https://www.alphavantage.co/query"

def get_intraday_data(symbol, interval="1min", output_size="compact"):
    params = {
        "function": "TIME_SERIES_INTRADAY",
        "symbol": f"{symbol}.NS",
        "interval": interval,
        "apikey": ALPHA_VANTAGE_API_KEY,
        "outputsize": output_size,
        "datatype": "json"
    }

    response = requests.get(BASE_URL, params=params)
    data = response.json()

    key = f"Time Series ({interval})"
    if key not in data:
        raise Exception(f"Alpha Vantage error or rate limit exceeded: {data}")

    df = pd.DataFrame(data[key]).T
    df.columns = ["Open", "High", "Low", "Close", "Volume"]
    df = df.astype(float)
    df.index = pd.to_datetime(df.index)
    df.sort_index(inplace=True)

    return df

def get_daily_data(symbol, output_size="compact"):
    params = {
        "function": "TIME_SERIES_DAILY_ADJUSTED",
        "symbol": f"{symbol}.NS",
        "apikey": ALPHA_VANTAGE_API_KEY,
        "outputsize": output_size,
        "datatype": "json"
    }

    response = requests.get(BASE_URL, params=params)
    data = response.json()

    key = "Time Series (Daily)"
    if key not in data:
        raise Exception(f"Alpha Vantage error or rate limit exceeded: {data}")

    df = pd.DataFrame(data[key]).T
    df.columns = [
        "Open", "High", "Low", "Close", "Adjusted Close",
        "Volume", "Dividend Amount", "Split Coefficient"
    ]
    df = df[["Open", "High", "Low", "Close", "Volume"]].astype(float)
    df.index = pd.to_datetime(df.index)
    df.sort_index(inplace=True)

    return df
