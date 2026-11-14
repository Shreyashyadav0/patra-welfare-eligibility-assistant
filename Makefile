.PHONY: help install test eval demo run clean

help:
	@echo "make install   install dependencies and the package (editable)"
	@echo "make test      run the test suite (47 tests)"
	@echo "make eval      run the benchmark and print the metrics table"
	@echo "make demo      ask one example question"
	@echo "make run       start the web interface on http://127.0.0.1:8000"
	@echo "make clean     remove caches and build artefacts"

install:
	python3 -m pip install -e ".[dev]"

test:
	python3 -m pytest -q

eval:
	python3 -m patra.cli eval --out artifacts/eval_report.json

demo:
	python3 -m patra.cli demo "I am a 45 year old farmer who does not pay income tax. Am I eligible for PM-KISAN?"

run:
	python3 -m patra.cli serve

clean:
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache *.egg-info build dist
