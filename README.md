# Market Prediction System

A machine learning trading project that predicts Buy/Sell signals using stock price data and technical indicators. Built with Python, SQLite, and Streamlit.

## Features
- Fetches stock price data (AAPL, MSFT, SPY) using Yahoo Finance
- Stores data in SQLite database
- Calculates technical indicators (RSI, MACD, EMAs)
- Machine learning model using Random Forest
- Backtesting system
- Interactive Streamlit dashboard

##  Stack
Python, Pandas, Scikit-learn, SQLite, YFinance, TA, Streamlit

## ✅ Project Structure
market-prediction-system/
├── data/
├── src/
│ ├── data/
│ ├── features/
│ ├── models/
├── app/
├── config.yaml
├── requirements.txt
├── Makefile

## Run Project
```bash
# Activate virtual environment
source venv/bin/activate

# Fetch stock data
make run-data

# Generate features
make run-features

# Train model
make train

# Backtest strategy
make backtest

# Run dashboard
make app
