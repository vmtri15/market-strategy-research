install:
	pip install -r requirements.txt

run-data:
	python src/data/fetch_data.py

run-features:
	python src/features/build_features.py

train:
	python src/models/train_model.py

backtest:
	python src/models/backtest.py

app:
	streamlit run app/dashboard.py
