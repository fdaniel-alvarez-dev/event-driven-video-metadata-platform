SHELL := /bin/bash

.PHONY: help up down logs test unit integration e2e fmt lint typecheck security local-demo deploy destroy

help:
	@echo "Targets:"
	@echo "  make up            Start local mock pipeline (docker compose)"
	@echo "  make down          Stop local stack"
	@echo "  make logs          Tail logs"
	@echo "  make test          Run unit+integration tests"
	@echo "  make e2e           Run local e2e test (requires docker)"
	@echo "  make lint          Ruff + Bandit"
	@echo "  make typecheck     Mypy"
	@echo "  make security      pip-audit (python)"
	@echo "  make deploy        Terraform apply (AWS mode)"
	@echo "  make destroy       Terraform destroy (AWS mode)"

up:
	docker compose up -d --build

down:
	docker compose down -v

logs:
	docker compose logs -f --tail=200

test:
	python3 -m pytest -q tests/unit tests/integration

unit:
	python3 -m pytest -q tests/unit

integration:
	python3 -m pytest -q tests/integration

e2e:
	bash scripts/run_e2e.sh

fmt:
	python3 -m ruff format .

lint:
	python3 -m ruff check .
	python3 -m bandit -q -r src

typecheck:
	python3 -m mypy src

security:
	python3 -m pip_audit -r requirements.txt

local-demo:
	bash scripts/demo_local.sh

deploy:
	bash scripts/deploy_aws.sh

destroy:
	bash scripts/destroy_aws.sh
