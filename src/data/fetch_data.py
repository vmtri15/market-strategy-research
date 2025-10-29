import yfinance as yf
import pandas as pd
from sqlalchemy import create_engine
import yaml
import os

# Load config
with open("config.yaml", "r") as file:
    config = yaml.safe_load(file)

DB_PATH = config["data"]["database"]
SYMBOLS = config["data"]["symbols"]
INTERVAL = config["data"]["interval"]
START_DATE = config["data"]["start_date"]

# Create database engine
engine = create_engine(f"sqlite:///{DB_PATH}")

def fetch_and_store(symbol):
    print(f"Fetching data for {symbol}...")
    df = yf.download(symbol, start=START_DATE, interval=INTERVAL)
    
    # Fix MultiIndex columns
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] for col in df.columns]

    df = df.rename(columns={
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Adj Close": "adj_close",
        "Volume": "volume"
    })

    df.reset_index(inplace=True)
    df["symbol"] = symbol

    df.to_sql("price_data", engine, if_exists="append", index=False)
    print(f"Stored {symbol} data in database.")

def main():
    # Delete database file to avoid conflicts
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    for symbol in SYMBOLS:
        fetch_and_store(symbol)

if __name__ == "__main__":
    main()
