import streamlit as st
import pandas as pd
import joblib
import yaml
import matplotlib.pyplot as plt

# Load config
with open("config.yaml", "r") as file:
    config = yaml.safe_load(file)

MODEL_PATH = config["model"]["save_path"]

st.title("📈 Market Prediction System")
st.subheader("ML-based Buy/Sell Signals for AAPL, MSFT, SPY")

@st.cache_data
def load_data():
    return pd.read_csv("data/processed/backtest_results.csv")

df = load_data()

# --- Sidebar filters ---
symbol_list = df["symbol"].unique()
selected_symbol = st.sidebar.selectbox("Select a stock:", symbol_list)

filtered_df = df[df["symbol"] == selected_symbol]

# --- Show prediction chart ---
st.write(f"### Price & Strategy Equity Curve for {selected_symbol}")
fig, ax1 = plt.subplots(figsize=(10, 5))
ax1.plot(filtered_df["Date"], filtered_df["close"], label="Close Price")
ax1.set_xlabel("Date")
ax1.set_ylabel("Price ($)")
ax1.legend(loc="upper left")

ax2 = ax1.twinx()
ax2.plot(filtered_df["Date"], filtered_df["equity"], color="green", label="Strategy Equity")
ax2.set_ylabel("Equity ($)")
ax2.legend(loc="upper right")

st.pyplot(fig)

# --- Show table of signals ---
st.write("### Recent Signals")
recent_signals = filtered_df[["Date", "close", "predicted_signal"]].tail(20)
st.dataframe(recent_signals)

