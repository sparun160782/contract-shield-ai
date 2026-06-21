.PHONY: help env-check cloud-auth install setup schema-setup seed-rules run-ingestion run-agent run-all lint format test clean clean-all

SHELL := cmd
.SHELLFLAGS := /C

PROJECT_ROOT := $(CURDIR)
INGESTION_DIR := $(PROJECT_ROOT)/contract-shield-ingestion
AGENT_DIR := $(PROJECT_ROOT)/contract-shield-agentic-be

help:
	@echo Contract Shield AI - Make Targets
	@echo.
	@echo setup and config:
	@echo   make env-check
	@echo   make cloud-auth
	@echo   make install
	@echo   make setup
	@echo.
	@echo pipeline:
	@echo   make schema-setup
	@echo   make seed-rules
	@echo   make run-ingestion
	@echo   make run-agent
	@echo   make run-all
	@echo.
	@echo quality:
	@echo   make lint
	@echo   make format
	@echo   make test
	@echo.
	@echo cleanup:
	@echo   make clean
	@echo   make clean-all

env-check:
	@python --version
	@gcloud --version
	@bq version
	@echo Environment check complete.

cloud-auth:
	@gcloud auth application-default login
	@gcloud auth list
	@gcloud config get-value project

install:
	@cd "$(INGESTION_DIR)" && python -m pip install -e .
	@cd "$(AGENT_DIR)" && python -m pip install -e .
	@echo Dependencies installed.

setup: env-check install schema-setup seed-rules
	@echo Setup complete.

schema-setup:
	@powershell -NoProfile -ExecutionPolicy Bypass -File "$(PROJECT_ROOT)/scripts/schema_setup.ps1" -SchemaPath "$(PROJECT_ROOT)/scripts/bigquery_schema.sql"
	@echo BigQuery schema setup complete.

seed-rules:
	@cd "$(INGESTION_DIR)" && python -m pip install -e . && python -m src.seed_rules
	@echo Risk rules seeded.																																																																																																																																																																																																																																																																																																																																																																																																																																																																																																													

run-ingestion:
	@cd "$(INGESTION_DIR)" && python -m pip install -e . && set INPUT_FOLDER=..\contract_input_pack && python -m src.main
	@echo Ingestion finished.

run-agent:
	@cd "$(AGENT_DIR)" && python main.py
	@echo Agent assessment finished.

run-all: run-ingestion run-agent
	@echo Full pipeline finished.

lint:
	@cd "$(INGESTION_DIR)" && python -m pip install -q flake8
	@cd "$(INGESTION_DIR)" && python -m flake8 src
	@cd "$(AGENT_DIR)" && python -m pip install -q flake8
	@cd "$(AGENT_DIR)" && python -m flake8 src main.py

format:
	@cd "$(INGESTION_DIR)" && python -m pip install -q black isort
	@cd "$(INGESTION_DIR)" && python -m black src
	@cd "$(INGESTION_DIR)" && python -m isort src
	@cd "$(AGENT_DIR)" && python -m pip install -q black isort
	@cd "$(AGENT_DIR)" && python -m black src main.py
	@cd "$(AGENT_DIR)" && python -m isort src main.py

test:
	@echo No tests configured yet.

clean:
	@powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-ChildItem -Path '$(PROJECT_ROOT)' -Recurse -Directory -Filter '__pycache__' | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue; Get-ChildItem -Path '$(PROJECT_ROOT)' -Recurse -Directory -Filter '.pytest_cache' | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue; Get-ChildItem -Path '$(PROJECT_ROOT)' -Recurse -File -Filter '*.pyc' | Remove-Item -Force -ErrorAction SilentlyContinue"
	@echo Clean complete.

clean-all: clean
	@powershell -NoProfile -ExecutionPolicy Bypass -Command "Remove-Item -Recurse -Force '$(PROJECT_ROOT)/.venv' -ErrorAction SilentlyContinue"
	@echo Clean-all complete.

.DEFAULT_GOAL := help
