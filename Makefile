.PHONY: doctor demo demo-offline verify install lint test clean

PYTHON ?= python
PIP ?= $(PYTHON) -m pip

install:
	$(PIP) install -e ".[dev]"

doctor:
	$(PYTHON) -m content_engine doctor

demo:
	$(PYTHON) -m content_engine demo --out out/demo

demo-offline:
	$(PYTHON) -m content_engine demo --out out/demo --offline-tts

verify: doctor demo-offline
	@echo VERIFY_OK

lint:
	$(PYTHON) -m ruff check src tests || true

test:
	$(PYTHON) -m pytest -q

clean:
	rm -rf workspace out/demo out/runs __pycache__ .pytest_cache
	find . -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
