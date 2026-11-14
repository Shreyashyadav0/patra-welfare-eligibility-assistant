#!/usr/bin/env bash
# Run the benchmark and write the artefacts used in the report.
set -e
python3 -m patra.cli eval --out artifacts/eval_report.json | tee artifacts/eval_table.txt
