"""FastAPI application: the three-tier interface described in the synopsis."""

from __future__ import annotations

import logging
import time
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from .corpus import load_corpus
from .logging_conf import configure_logging
from .pipeline import Pipeline
from .settings import CORPUS_DIR, CRITERIA_DIR

configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="Patra - welfare scheme eligibility assistant", version="1.0.0")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

_corpus = load_corpus(CORPUS_DIR, CRITERIA_DIR)
_pipeline = Pipeline(_corpus)
logger.info(
    "corpus loaded: %d schemes, %d chunks, version %s",
    len(_corpus.schemes),
    len(_corpus.chunks),
    _corpus.corpus_version,
)


@app.middleware("http")
async def log_requests(request, call_next):
    """One line per request: method, path, status and duration."""
    started = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - started) * 1000
    logger.info(
        "%s %s -> %d in %.1f ms", request.method, request.url.path, response.status_code, elapsed_ms
    )
    return response


class Query(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    lang: str = Field(default="en", pattern="^(en|hi)$")
    profile: dict | None = None


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "corpus_version": _corpus.corpus_version,
        "schemes": len(_corpus.schemes),
        "chunks": len(_corpus.chunks),
    }


@app.get("/schemes")
def schemes() -> list[dict]:
    return [
        {
            "scheme_id": s.scheme_id,
            "name": s.name,
            "ministry": s.ministry,
            "level": s.level,
            "state": s.state,
            "official_url": s.official_url,
            "criteria": [c.as_dict() for c in s.criteria],
            "source_note": s.source_note,
        }
        for s in _corpus.schemes.values()
    ]


@app.post("/query")
def query(payload: Query) -> dict:
    answer = _pipeline.answer(payload.question, profile=payload.profile, lang=payload.lang)
    result = dict(answer.rendered)
    result.update(
        {
            "scheme_id": answer.scheme_id,
            "corpus_version": _corpus.corpus_version,
            "latency_ms": round(answer.latency_ms, 1),
            "features": answer.features,
        }
    )
    return result


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "schemes": list(_corpus.schemes.values()),
            "result": None,
            "question": "",
        },
    )


@app.post("/", response_class=HTMLResponse)
def ask(request: Request, question: str = Form(...), lang: str = Form("en")):
    if not question.strip():
        raise HTTPException(status_code=400, detail="question is empty")
    answer = _pipeline.answer(question, lang=lang)
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "schemes": list(_corpus.schemes.values()),
            "result": answer.rendered,
            "question": question,
            "latency_ms": round(answer.latency_ms, 1),
            "scheme": answer.scheme_name,
        },
    )
