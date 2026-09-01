PYTHON ?= python3.12
VENV ?= .venv
TCR_REGISTRY ?= ccr.ccs.tencentyun.com
TCR_NAMESPACE ?= your-namespace
TCR_IMAGE ?= unmc-rag
TCR_TAG ?= latest
APP_IMAGE ?= $(TCR_REGISTRY)/$(TCR_NAMESPACE)/$(TCR_IMAGE):$(TCR_TAG)

.PHONY: install test lint run docker-up docker-down docker-build docker-push

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
	docker compose -f docker-compose.yaml -f compose.local.yaml up --build

docker-down:
	docker compose down

docker-build:
	docker build -t $(APP_IMAGE) -t $(TCR_IMAGE):$(TCR_TAG) .

docker-push: docker-build
	docker push $(APP_IMAGE)
