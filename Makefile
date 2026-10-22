# `make all` needs network access (yfinance).
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

research:
	python -m src.models.research

# Full rebuild: download prices, features, model, research, report.
all: run-data run-features train research report

test:
	python -m unittest discover -s tests -v

report:
	python -m src.models.business_report

paper:
	python -m src.paper.engine run

paper-check:
	python -m src.paper.engine check
