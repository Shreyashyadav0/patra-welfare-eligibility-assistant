"""Command line: demo a question, run the benchmark, or serve the API."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .corpus import load_corpus
from .evaluate import format_table, freetext_mode, load_bench, run
from .pipeline import Pipeline
from .settings import BENCH_FILE, CORPUS_DIR, CRITERIA_DIR


def _pipeline() -> Pipeline:
    return Pipeline(load_corpus(CORPUS_DIR, CRITERIA_DIR))


def cmd_demo(args) -> None:
    pipeline = _pipeline()
    answer = pipeline.answer(args.question, lang=args.lang)
    out = answer.rendered
    print(f"\nQ: {args.question}\n")
    print(f"A: {out['answer']}")
    print(f"   decision={out['decision']}  verdict={out['verdict_type']}  "
          f"reason={out['reason_code']}  p={out['probability']}")
    for c in out["criteria"]:
        print(f"   - {c['field']:16s} {str(c['observed']):12s} {c['operator']:3s} "
              f"{str(c['threshold']):10s} -> {c['outcome']}")
    print(f"\n   citations: {len(out['citations'])}  latency: {answer.latency_ms:.1f} ms\n")


def cmd_eval(args) -> None:
    pipeline = _pipeline()
    items = load_bench(BENCH_FILE)
    result = run(pipeline, items)
    print(format_table(result))
    ft = freetext_mode(pipeline, items)
    print(f"\nfree-text mode (profile parsed from the question): "
          f"{ft['verdict_accuracy_freetext']:.2f} accuracy over {ft['n']} items, "
          f"{ft['asked_for_missing_field']} asked for a missing field")
    print(f"retrieval-only recall@5 (before clause injection): "
          f"{result['metrics']['retrieval_only_recall_at_5']:.2f}")
    print(f"CLVC: kappa {result['metrics']['clvc_kappa']} over {result['metrics']['clvc_pairs']} pairs, "
          f"raw agreement {result['metrics']['clvc_raw_agreement']}")
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"\nwrote {args.out}")


def cmd_serve(args) -> None:
    import uvicorn
    uvicorn.run("patra.api:app", host=args.host, port=args.port, reload=False)


def main() -> None:
    parser = argparse.ArgumentParser(prog="patra", description="Patra eligibility assistant")
    sub = parser.add_subparsers(dest="command", required=True)

    d = sub.add_parser("demo", help="answer one question")
    d.add_argument("question")
    d.add_argument("--lang", default="en", choices=["en", "hi"])
    d.set_defaults(func=cmd_demo)

    e = sub.add_parser("eval", help="run PatraBench and print the metrics table")
    e.add_argument("--out", default="artifacts/eval_report.json")
    e.set_defaults(func=cmd_eval)

    s = sub.add_parser("serve", help="serve the web interface")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    s.set_defaults(func=cmd_serve)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
