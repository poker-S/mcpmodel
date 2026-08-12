.PHONY: bootstrap check validate pilot baseline test lint

bootstrap:
	./scripts/bootstrap.sh

check:
	.venv/bin/python scripts/check_environment.py

validate:
	.venv/bin/mcpmodel-validate data/examples

pilot:
	.venv/bin/python scripts/generate_pilot.py

baseline:
	.venv/bin/python scripts/run_baselines.py --output results/p1-smoke

test:
	.venv/bin/pytest

lint:
	.venv/bin/ruff check .
