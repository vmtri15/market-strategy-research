import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
import joblib
import yaml

# Load config
with open("config.yaml", "r") as file:
    config = yaml.safe_load(file)

MODEL_PATH = config["model"]["save_path"]

def load_features():
    return pd.read_csv("data/processed/features.csv")

def train_model():
    df = load_features()

    features = ["rsi", "macd", "macd_signal", "ema_20", "ema_50"]
    X = df[features]
    y = df["signal"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, shuffle=False
    )

    model = RandomForestClassifier(n_estimators=200, random_state=42)
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    print("✅ Model Evaluation:")
    print(classification_report(y_test, preds))

    joblib.dump(model, MODEL_PATH)
    print(f"✅ Model saved to {MODEL_PATH}")

if __name__ == "__main__":
    train_model()
