#!/usr/bin/env bash
# Three questions that show the three answer states. Run from the repo root.
set -e
echo "--- 1. eligible ---------------------------------------------------"
python3 -m patra.cli demo "I am a 45 year old farmer who does not pay income tax and I am not a government employee. Am I eligible for PM-KISAN?"
echo "--- 2. not eligible -----------------------------------------------"
python3 -m patra.cli demo "I pay income tax and I am a farmer. Am I eligible for PM-KISAN?"
echo "--- 3. abstain (scheme not held) ----------------------------------"
python3 -m patra.cli demo "Am I eligible for the Kerala widow pension scheme?"
