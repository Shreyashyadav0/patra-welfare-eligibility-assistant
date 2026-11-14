# Patra — Welfare Scheme Eligibility Assistant

Ask a question about an Indian welfare scheme and get a **verdict**, not a paragraph:
*eligible*, *not eligible*, *indeterminate*, or *abstained*. Every verdict shows the
criteria that decided it and quotes the clause behind each one.

The verdict is computed by a deterministic rule engine over a curated criteria table.
A language model may read the question; it never states a threshold and never decides.

> **Project:** IGNOU MCA (MCA_NEW), course MCSP-232, 12 credits.
> **Category:** Artificial Intelligence / Machine Learning / Data Science.

---

## What an answer looks like

```
Q: I am a 45 year old farmer who does not pay income tax and I am not
   a government employee. Am I eligible for PM-KISAN?

A: You appear to be eligible for PM-KISAN.

   occupation         farmer     ==  farmer     -> pass
   age                45         >=  18         -> pass
   income_tax_payer   no         IS_FALSE      -> pass
   govt_employee      no         IS_FALSE      -> pass

   citations: 4     latency: 4.1 ms
```

When it cannot decide, it says so and asks for exactly the missing field. When the
documents do not cover the question, it abstains rather than guessing.

---

## Quickstart

```bash
make install          # dependencies + editable install
make test             # 47 tests
make eval             # benchmark, prints the metrics table
make demo             # one worked question
make run              # web interface on http://127.0.0.1:8000
```

Without `make`:

```bash
python3 -m pip install -e ".[dev]"
python3 -m pytest -q
python3 -m patra.cli demo "Am I eligible for PM-KISAN if I am a farmer?"
python3 -m patra.cli serve
```

Runs fully offline: no API key, no model download, no database server.

---

## What is in this repository

```
.
├── README.md                  ← you are here
├── Makefile                   ← the five commands above
├── pyproject.toml             ← packaging, dependencies, pytest config
├── requirements.txt           ← pinned versions for a plain pip install
├── Dockerfile                 ← container build
├── LICENSE                    ← MIT
│
├── src/patra/                 ← THE APPLICATION (all code lives here)
│   ├── engine.py              ← the verdict engine: 10 operators, no model call
│   ├── gate.py                ← abstention gate: logistic calibrator + threshold rule
│   ├── pipeline.py            ← retrieve → extract → evaluate → gate → compose
│   ├── corpus.py              ← ingestion, chunking, clause-span resolution
│   ├── index.py               ← BM25, vector index, rank fusion
│   ├── retrieve.py            ← hybrid retrieval + lexical reranking
│   ├── extract.py             ← profile extraction, criteria proposal
│   ├── link.py                ← scheme name matching (English + Devanagari)
│   ├── compose.py             ← answer text and citations
│   ├── evaluate.py            ← benchmark harness, 13 metrics
│   ├── api.py                 ← FastAPI routes
│   ├── cli.py                 ← demo / eval / serve
│   ├── settings.py            ← every tunable, one file
│   └── templates/index.html   ← the web page
│
├── data/                      ← everything the system reads
│   ├── corpus/*.md            ← 6 scheme documents (illustrative seed data)
│   ├── criteria/*.json        ← curated criteria table, each tied to a clause
│   └── bench/patrabench_demo.jsonl ← 46 benchmark questions with gold answers
│
├── tests/                     ← 47 tests, five files, one per component
│   ├── test_engine.py         ← truth table: boundaries, conflicts, type mismatch
│   ├── test_corpus.py         ← every clause must resolve to its document
│   ├── test_extract.py        ← parsing questions, including negation
│   ├── test_gate.py           ← threshold rule, coverage floor
│   └── test_api.py            ← HTTP routes and validation
│
├── docs/                      ← the university paperwork
│   ├── MCSP-232_Project_Report.docx   ← 109-page report
│   ├── MCSP-232_Synopsis.docx         ← approved proposal
│   ├── Project_Defence_Brief.docx     ← viva preparation
│   └── SUBMISSION_CHECKLIST.md        ← what to hand in, what to fill in
│
├── scripts/
│   ├── demo.sh                ← the three answer states, end to end
│   └── evaluate.sh            ← regenerate the artefacts in artifacts/
│
└── artifacts/                 ← output of the last evaluation run
    ├── eval_report.json       ← per-item results and metrics
    └── eval_table.txt         ← the printed metrics table
```

**Reading order if you are new to this:** `README` → `data/criteria/pmkisan.json`
(what a criteria table looks like) → `src/patra/engine.py` (how a verdict is computed)
→ `tests/test_engine.py` (what the engine promises) → `docs/`.

---

## How it works

1. **Link** the scheme named in the question (`link.py`).
2. **Retrieve** candidate paragraphs with BM25 and a TF-IDF vector index, fused by
   reciprocal rank, then reranked lexically (`index.py`, `retrieve.py`).
3. **Extract** the profile from the question — age, income, category, occupation —
   and the criteria table from the curated JSON (`extract.py`).
4. **Evaluate** deterministically: any failed mandatory condition settles the verdict;
   an unknown alone does not; two clauses that admit no common value are a conflict
   (`engine.py`).
5. **Gate**: a calibrated score over eight features decides whether the evidence
   supports showing the verdict at all (`gate.py`).
6. **Compose** the answer, with the clause text for every criterion (`compose.py`).

---

## Measured results

From `make eval` on the 46-item demo benchmark. Targets are from the synopsis; a miss
is reported as a miss.

| Metric | Measured | Target | |
|---|---|---|---|
| Recall@5, evidence to the engine | 0.97 | ≥ 0.85 | meets |
| Recall@5, retrieval only | 0.33 | — | diagnostic |
| Verdict accuracy (answered answerable items) | 1.00 | ≥ 0.80 | meets |
| Coverage (answerable items) | 0.78 | — | diagnostic |
| Selective accuracy (answerable items) | 0.78 | ≥ 0.85 | **misses** |
| Accuracy over all 46 items | 0.67 | — | diagnostic |
| Selective accuracy over all answered items | 0.91 | ≥ 0.85 | meets |
| Unnecessary abstention | 0.23 | ≤ 0.15 | **misses** |
| Abstention on the six unanswerable items | 0.50 | 1.00 | **misses** |
| Expected calibration error (5 bins) | 0.35 | ≤ 0.10 | **misses** |
| Excess AURC | 0.05 | ≤ 0.12 | meets |
| Cross-lingual raw agreement (κ 0.00) | 0.00 | ≥ 0.80 | **misses** |
| p95 in-process latency | 3.4 ms | ≤ 8000 ms | meets |

Two things to read carefully. Verdict accuracy is 1.00 because the engine is marked
against the table it evaluates — the honest end-to-end figures are 0.67 over all items
and 0.91 selective over everything answered. And recall@5 of 0.97 counts the criteria
table's own clauses being added to the evidence; 0.33 is what the retriever achieves
alone. Both numbers are published so the difference is visible.

---

## What this does not do

- **Six schemes, not 300.** The corpus is illustrative seed data written for the demo,
  not an authoritative copy of scheme guidelines. Replace it before any real use.
- **No personal data is stored.** No login, no database, nothing kept after a request.
- **Not an official service.** It is an advisory university project; the scheme portal
  is the authority.
- **The gate abstains on half the out-of-scope questions**, not all of them. A scope
  classifier is the next component.
- **The Hindi path is weak.** A lexical index over English text retrieves little for
  Devanagari, so Hindi questions fall below the gate. A multilingual embedder is the fix.

---

## Adding a real scheme

Three steps, no code:

1. Put the official document in `data/corpus/<scheme>-<year>.md` with front matter
   (`doc_id`, `scheme_id`, `title`, `source_url`, `retrieved_on`).
2. Add `data/criteria/<scheme>.json`. Every `clause_text` must be an **exact substring**
   of the document — ingestion fails loudly if it is not, which is the point.
3. Add the scheme's aliases to `src/patra/link.py`, English and Devanagari.

Then `make eval` to see the effect.

---

## Swapping in the real models

- **Embeddings:** replace `VectorIndex` in `src/patra/index.py` with any class exposing
  `search(query, k) -> [(chunk_id, score)]`, e.g. BGE-M3. Nothing else changes.
- **Reranker:** replace `HybridRetriever.rerank` with a cross-encoder call.
- **Extraction:** implement `LLMProfileExtractor.extract` returning an `Extraction`. The
  pipeline already treats a missing field as `unknown`, which is what makes the gate work.

---

## Documents

| File | What it is |
|---|---|
| `docs/MCSP-232_Project_Report.docx` | The bound report: 11 chapters, 8 appendices, 109 pages |
| `docs/MCSP-232_Synopsis.docx` | The approved project proposal |
| `docs/Project_Defence_Brief.docx` | Viva preparation: novelty position, 15 questions |
| `docs/SUBMISSION_CHECKLIST.md` | What to submit, what still needs filling in |

The report and synopsis still have blank fields for enrolment number, study centre,
regional centre and the guide's name and signature. They are yours to complete.

---

## Tech stack

Python 3.12 · FastAPI · Jinja2 · scikit-learn (TF-IDF, logistic regression, GroupKFold)
· NumPy · pytest. No GPU, no external services.

---

## Author

**Shreyash Yadav** — IGNOU MCA (MCA_NEW), MCSP-232 project.

Licensed under the MIT License; see `LICENSE`. The scheme documents in `data/corpus/`
remain the property of their publishers and are included as illustrative extracts.
