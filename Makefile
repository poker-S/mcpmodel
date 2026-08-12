.PHONY: bootstrap check validate test lint

bootstrap:
	./scripts/bootstrap.sh

check:
	.venv/bin/python scripts/check_environment.py

validate:
	.venv/bin/mcpmodel-validate data/examples

test:
	.venv/bin/pytest

lint:
	.venv/bin/ruff check .
