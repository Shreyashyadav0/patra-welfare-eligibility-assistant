# MCSP-232 submission package — what is here and what you must fill

## The five deliverables

| # | File | What it is | Status |
|---|---|---|---|
| 1 | `MCSP-232_Project_Report_Patra.docx` | The project report, 107 A4 pages, 11 chapters + 8 appendices | Ready except front matter |
| 2 | `MCSP-232_Synopsis_Patra.docx` | The approved-topic synopsis (proposal document, 21 pages) | Ready except front matter |
| 3 | `Patra_Project_Defence_Brief.docx` | Viva preparation: novelty position, 15 questions, build order | Ready |
| 4 | `Patra_Project_v1.zip` | The working software: 52 files, 44 passing tests, offline | Ready |
| 5 | `SUBMISSION_CHECKLIST.md` | This file | — |

## What YOU must fill in before posting

1. **Cover page** — enrolment number, study centre, regional centre, guide's name and designation, session.
2. **Certificate of originality** — your signature, your guide's signature, guide's name and designation, both dates. The signature must match the one on your approved proforma.
3. **Table of contents** — open the .docx in Word, press Ctrl+A then F9, and choose "update entire table" so the page numbers fill in.
4. **Screenshots** — run `python -m patra.cli serve`, open http://127.0.0.1:8000, and capture four screens (home, eligible answer, not-eligible answer, abstention). Insert them in Chapter 11 and reference them as Figures 11.1-11.4. This is the one piece of evidence the report does not yet carry.
5. **Corpus** — the six schemes are illustrative. Replace them with official documents and exact clause text before the viva, or state plainly in the viva that they are a seed set. The report already says so in Chapter 1 and Appendix C.

## What to put on the disc

* the `patra/` folder from the zip, unzipped
* `RUN.txt` containing:
```
python3 -m pip install -r requirements.txt
python3 -m pytest tests -q
python3 -m patra.cli eval
python3 -m patra.cli serve      # http://127.0.0.1:8000
```
* `artifacts/eval_report.json` and `artifacts/eval_table.txt` from your final run
* a copy of the report PDF, for convenience

Everything runs offline. No model download, no API key, no database server.

## Honest state of the submission

* **Length.** 107 pages total; about 85 pages excluding the code listings in Appendices E and H. The guideline asks for 100-125 pages excluding coding, so the documentation is roughly 15 pages short. Two ways to close it: add a Chapter 12 with two worked end-to-end walkthroughs, or move the Appendix H listings into Chapter 6 where they count as coding. Neither is done here.
* **Benchmark.** 46 items, not the 200 the synopsis plans. The report says so in Chapters 7, 8 and 10.
* **Corpus.** Six illustrative schemes, not 300. Stated throughout.
* **Two metrics miss.** ECE 0.29 against a target of 0.10, and cross-lingual kappa 0.00 over six pairs. A third quantity, abstention on unanswerable items, is 0.00. All three are reported as failures, not hidden.
* **Audit trail.** The report was audited twice by independent reviewers; the first round found a set of contradictions between chapters (a database described in Chapter 5 that Chapter 9 denied, a verdict vocabulary the code does not use, a metric claimed but not computed) and the second found the residue of those. All are now fixed. What the second round still flags is the front matter (yours to fill) and the length above.
