.PHONY: install test demo serve

PYTHON ?= python3
VENV ?= .venv

install:
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/pip install -e ".[dev]"

test:
	$(VENV)/bin/pytest -q

demo: install
	STUDYPILOT_DEMO=1 $(VENV)/bin/studypilot serve

serve:
	$(VENV)/bin/studypilot serve
