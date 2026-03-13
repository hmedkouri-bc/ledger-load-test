.PHONY: install proto test clean run-balance run-append run-mixed run-stress

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
LOCUST := $(VENV)/bin/locust
PYTEST := $(VENV)/bin/pytest

# Default config
CONFIG ?= config/local.yaml

install: $(VENV)/bin/activate

$(VENV)/bin/activate:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"

proto:
	PYTHON=$(PYTHON) bash scripts/generate_proto.sh

test:
	PYTHONPATH=.:generated $(PYTEST) tests/ -v

clean:
	rm -rf generated/ledger/*.py generated/ledger/*.pyi
	rm -rf __pycache__ src/__pycache__ tests/__pycache__ locustfiles/__pycache__
	rm -rf .pytest_cache *.egg-info

# Scenario runners — headless mode for CI / quick validation
run-balance:
	PYTHONPATH=.:generated CONFIG_PATH=$(CONFIG) $(LOCUST) -f locustfiles/balance_check.py --headless -u 1 -r 1 -t 30s

run-append:
	PYTHONPATH=.:generated CONFIG_PATH=$(CONFIG) $(LOCUST) -f locustfiles/append_transaction.py --headless -u 1 -r 1 -t 30s

run-mixed:
	PYTHONPATH=.:generated CONFIG_PATH=$(CONFIG) $(LOCUST) -f locustfiles/mixed_workload.py --headless -u 1 -r 1 -t 30s

run-stress:
	PYTHONPATH=.:generated CONFIG_PATH=$(CONFIG) $(LOCUST) -f locustfiles/stress_test.py --headless -u 1 -r 1 -t 30s

# Web UI mode
run-ui:
	PYTHONPATH=.:generated CONFIG_PATH=$(CONFIG) $(LOCUST) -f locustfiles/mixed_workload.py
