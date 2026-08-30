PYTHON ?= python3.12
VENV ?= .venv

.PHONY: install test lint run docker-up docker-down

install:
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/python -m pip install -e '.[dev]'

test:
	$(VENV)/bin/pytest

lint:
	$(VENV)/bin/ruff check .
	$(VENV)/bin/ruff format --check .

run:
	$(VENV)/bin/uvicorn app.main:app --reload

docker-up:
	docker compose up --build

docker-down:
	docker compose down
