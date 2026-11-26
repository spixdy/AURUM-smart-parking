.PHONY: setup train test lint site run sim-history up down demo

setup:        ## create venv and install everything
	python -m venv .venv && . .venv/bin/activate && pip install -r requirements-dev.txt
train:        ## train and save the model
	python -m aurum.model train
test:
	pytest --cov=aurum
lint:
	ruff check .
site:         ## rebuild web/index.html
	python scripts/build_site.py
run:          ## dashboard on http://localhost:8501
	streamlit run streamlit_app.py
sim-history:  ## 3 days of demo readings straight into the database
	python -m aurum.simulator --offline --backfill 3
up:
	docker compose up -d --build
demo:         ## full stack plus the sensor simulator
	docker compose --profile demo up -d --build
down:
	docker compose down
