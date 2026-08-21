.DEFAULT_GOAL := help
VENV ?= .venv
PY   ?= $(VENV)/bin/python

help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

setup: ## Create a virtualenv and install runtime + dev dependencies
	python3 -m venv $(VENV)
	$(PY) -m pip install -U pip
	$(PY) -m pip install -r requirements-dev.txt
	$(PY) -m pip install -e .

api: ## Run the API with reload on :8000
	$(PY) -m uvicorn verbatim.api.app:app --reload --port 8000

web: ## Run the Vite dev server on :5173
	cd web && npm install && npm run dev

ingest: ## Ingest a folder: make ingest SRC=./samples
	$(PY) -m verbatim.cli ingest $(SRC)

test: ## Run the test suite
	$(PY) -m pytest -q

lint: ## Lint and format-check
	$(PY) -m ruff check verbatim tests
	$(PY) -m ruff format --check verbatim tests

fmt: ## Auto-format
	$(PY) -m ruff format verbatim tests
	$(PY) -m ruff check --fix verbatim tests

eval: ## Run the retrieval evaluation harness
	$(PY) -m verbatim.eval.run_eval eval/questions.jsonl

clean: ## Remove build/test caches
	rm -rf .pytest_cache .ruff_cache **/__pycache__ htmlcov .coverage

.PHONY: help setup api web ingest test lint fmt eval clean
