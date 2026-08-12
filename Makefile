.PHONY: bootstrap check validate pilot annotation-pack ingest baseline test lint

bootstrap:
	./scripts/bootstrap.sh

check:
	.venv/bin/python scripts/check_environment.py

validate:
	.venv/bin/mcpmodel-validate data/examples

pilot:
	.venv/bin/python scripts/generate_pilot.py

annotation-pack:
	.venv/bin/python scripts/create_annotation_pack.py --output results/annotation-pack

ingest:
	.venv/bin/python scripts/ingest_chaitin.py \
		--extracted-root ../thesis/datasets/chaitin_extracted \
		--raw-root ../thesis/datasets/chaitin_raw \
		--output data/derived/chaitin-0.1

baseline:
	.venv/bin/python scripts/run_baselines.py --output results/p1-smoke

test:
	.venv/bin/pytest

lint:
	.venv/bin/ruff check .
