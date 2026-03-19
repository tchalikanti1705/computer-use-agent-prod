SHELL := /bin/bash

.PHONY: up down build test migrate

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

test:
	python -m pytest tests/ -v

migrate:
	python -m scripts.migrate

dev-gateway:
	uvicorn gateway.app:app --reload --port 8000

dev-worker:
	python -m agent_runtime.worker
