import pandas as pd
from sqlalchemy import create_engine
import yaml
import ta

# Load config
with open("config.yaml", "r") as file:
    config = yaml.safe_load(file)

DB_PATH = config["data"]["database"]
PREDICTION_HORIZON = config["features"]["prediction_horizon"]

engine = create_engine(f"sqlite:///{DB_PATH}")

def load_data():
    query = "SELECT * FROM price_data"
    return pd.read_sql(query, engine)

def add_indicators(df):
    df = df.sort_values(by=["symbol", "Date"])

    # RSI
    df["rsi"] = ta.momentum.RSIIndicator(close=df["close"]).rsi()

    # MACD
    macd = ta.trend.MACD(close=df["close"])
    df["macd"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()
    df["macd_hist"] = macd.macd_diff()

    # EMA
    df["ema_20"] = ta.trend.EMAIndicator(close=df["close"], window=20).ema_indicator()
    df["ema_50"] = ta.trend.EMAIndicator(close=df["close"], window=50).ema_indicator()

    return df

def add_target(df):
    df["future_return"] = df.groupby("symbol")["close"].shift(-PREDICTION_HORIZON) / df["close"] - 1
    df["signal"] = df["future_return"].apply(lambda x: 1 if x > 0.02 else -1 if x < -0.02 else 0)
    return df

def save_features(df):
    df.to_csv("data/processed/features.csv", index=False)
    print("✅ Features saved to data/processed/features.csv")

def main():
    df = load_data()
    df = add_indicators(df)
    df = add_target(df)
    df.dropna(inplace=True)
    save_features(df)

if __name__ == "__main__":
    main()
