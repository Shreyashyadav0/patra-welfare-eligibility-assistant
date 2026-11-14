"""Runtime settings. Everything here is overridable by environment variable."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent          # src/patra
REPO_ROOT = BASE_DIR.parents[1]                      # repository root
DATA_DIR = Path(os.environ.get("PATRA_DATA", REPO_ROOT / "data"))
if not DATA_DIR.exists():                            # packaged fallback
    DATA_DIR = BASE_DIR / "data"
CORPUS_DIR = DATA_DIR / "corpus"
CRITERIA_DIR = DATA_DIR / "criteria"
BENCH_FILE = DATA_DIR / "bench" / "patrabench_demo.jsonl"

# Retrieval
BM25_K1 = 1.5
BM25_B = 0.75
RRF_K = 60
CANDIDATES = 50
RERANK_TOP = 10

# Gate
GATE_TARGET_ACCURACY = 0.80   # accuracy target used to pick the abstention threshold
GATE_MIN_COVERAGE = 0.80      # answer at least 80% of questions

# Abstention when no scheme is named in the question
UNLINKED_MIN_RERANK = 0.60   # below this, an unlinked question is out of scope

# Answer composition
DISCLAIMER = (
    "This is an advisory tool built for a university project. It is not an official "
    "government service. The scheme portal is the final authority."
)
