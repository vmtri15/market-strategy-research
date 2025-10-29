import pandas as pd
import joblib
import yaml

# Load config
with open("config.yaml", "r") as file:
    config = yaml.safe_load(file)

MODEL_PATH = config["model"]["save_path"]
INITIAL_BALANCE = config["backtest"]["initial_balance"]
TRANSACTION_COST = config["backtest"]["transaction_cost"]

def load_features():
    return pd.read_csv("data/processed/features.csv")

def run_backtest():
    df = load_features()

    model = joblib.load(MODEL_PATH)
    features = ["rsi", "macd", "macd_signal", "ema_20", "ema_50"]
    df["predicted_signal"] = model.predict(df[features])

    balance = INITIAL_BALANCE
    position = 0
    entry_price = 0
    equity_curve = []

    for _, row in df.iterrows():
        price = row["close"]

        # Buy
        if row["predicted_signal"] == 1 and position == 0:
            position = balance / price
            balance = 0

        # Sell
        elif row["predicted_signal"] == -1 and position > 0:
            balance = position * price * (1 - TRANSACTION_COST)
            position = 0

        total_value = balance + position * price
        equity_curve.append(total_value)

    df["equity"] = equity_curve
    df.to_csv("data/processed/backtest_results.csv", index=False)
    print("✅ Backtest complete. Results saved to data/processed/backtest_results.csv")

if __name__ == "__main__":
    run_backtest()
