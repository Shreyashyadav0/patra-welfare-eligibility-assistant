"""Corpus ingestion: documents, chunks, and clause-span resolution.

A clause span is resolved by locating the exact clause text inside the document at
ingest time. If a clause cannot be located, ingestion fails loudly rather than
silently producing a criterion with no evidence - that failure mode is the one the
project exists to prevent.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class CorpusError(RuntimeError):
    """Raised when corpus data is internally inconsistent."""


@dataclass(frozen=True)
class Document:
    doc_id: str
    scheme_id: str
    title: str
    source_url: str
    retrieved_on: str
    text: str
    sha256: str


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    doc_id: str
    scheme_id: str
    text: str
    span_start: int
    span_end: int
    section: str


@dataclass(frozen=True)
class Criterion:
    criterion_id: str
    scheme_id: str
    field: str
    criterion_type: str
    operator: str
    threshold: Any
    mandatory: bool
    clause_text: str
    span_start: int
    span_end: int
    doc_id: str

    def as_dict(self) -> dict:
        return {
            "criterion_id": self.criterion_id,
            "scheme_id": self.scheme_id,
            "field": self.field,
            "criterion_type": self.criterion_type,
            "operator": self.operator,
            "threshold": self.threshold,
            "mandatory": self.mandatory,
            "clause_text": self.clause_text,
            "span": [self.span_start, self.span_end],
            "doc_id": self.doc_id,
        }


@dataclass
class Scheme:
    scheme_id: str
    name: str
    ministry: str
    level: str
    state: str | None
    official_url: str
    source_note: str
    criteria: list[Criterion] = field(default_factory=list)


@dataclass
class Corpus:
    schemes: dict[str, Scheme]
    documents: dict[str, Document]
    chunks: list[Chunk]
    corpus_version: str

    def chunks_for_scheme(self, scheme_id: str) -> list[Chunk]:
        return [c for c in self.chunks if c.scheme_id == scheme_id]

    def chunk_by_id(self, chunk_id: str) -> Chunk:
        for c in self.chunks:
            if c.chunk_id == chunk_id:
                return c
        raise KeyError(chunk_id)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _chunk_document(doc: Document) -> list[Chunk]:
    """Split on blank lines, keeping character offsets so spans stay exact."""
    chunks: list[Chunk] = []
    pos = 0
    section = "body"
    for para in re.split(r"\n\s*\n", doc.text):
        if not para.strip():
            pos += len(para) + 2
            continue
        start = doc.text.find(para, pos)
        if start < 0:
            raise CorpusError(f"chunking lost position in {doc.doc_id}")
        end = start + len(para)
        heading = re.match(r"^(#{1,6})\s+(.*)$", para.strip())
        if heading:
            section = heading.group(2).strip()
        chunks.append(
            Chunk(
                chunk_id=f"{doc.doc_id}#{len(chunks)}",
                doc_id=doc.doc_id,
                scheme_id=doc.scheme_id,
                text=para.strip(),
                span_start=start,
                span_end=end,
                section=section,
            )
        )
        pos = end
    return chunks


def load_corpus(corpus_dir: Path, criteria_dir: Path) -> Corpus:
    """Load every scheme document and its curated criteria table."""
    documents: dict[str, Document] = {}
    schemes: dict[str, Scheme] = {}
    chunks: list[Chunk] = []
    manifest: list[str] = []

    for path in sorted(corpus_dir.glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        meta: dict[str, str] = {}
        body = raw
        if raw.startswith("---"):
            _, front, body = raw.split("---", 2)
            for line in front.strip().splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip()
        doc_id = meta.get("doc_id", path.stem)
        scheme_id = meta.get("scheme_id", path.stem)
        doc = Document(
            doc_id=doc_id,
            scheme_id=scheme_id,
            title=meta.get("title", doc_id),
            source_url=meta.get("source_url", ""),
            retrieved_on=meta.get("retrieved_on", "1970-01-01"),
            text=body,
            sha256=_sha256(body),
        )
        documents[doc_id] = doc
        chunks.extend(_chunk_document(doc))
        manifest.append(f"{doc_id}:{doc.sha256}")

    for path in sorted(criteria_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        scheme = Scheme(
            scheme_id=payload["scheme_id"],
            name=payload["name"],
            ministry=payload.get("ministry", ""),
            level=payload.get("level", "central"),
            state=payload.get("state"),
            official_url=payload.get("official_url", ""),
            source_note=payload.get("source_note", ""),
        )
        doc_id = payload["doc_id"]
        if doc_id not in documents:
            raise CorpusError(f"{path.name} references unknown document {doc_id}")
        text = documents[doc_id].text
        for i, c in enumerate(payload["criteria"], start=1):
            clause = c["clause_text"].strip()
            start = text.find(clause)
            if start < 0:
                raise CorpusError(
                    f"clause not found in {doc_id}: {clause[:60]!r} - "
                    "criteria must quote the document exactly"
                )
            scheme.criteria.append(
                Criterion(
                    criterion_id=f"{scheme.scheme_id}-C{i}",
                    scheme_id=scheme.scheme_id,
                    field=c["field"],
                    criterion_type=c.get("criterion_type", "other"),
                    operator=c["operator"],
                    threshold=c.get("threshold"),
                    mandatory=bool(c.get("mandatory", True)),
                    clause_text=clause,
                    span_start=start,
                    span_end=start + len(clause),
                    doc_id=doc_id,
                )
            )
        schemes[scheme.scheme_id] = scheme

    if not schemes:
        raise CorpusError("no schemes loaded")
    version = hashlib.sha256("|".join(sorted(manifest)).encode()).hexdigest()[:12]
    return Corpus(schemes=schemes, documents=documents, chunks=chunks, corpus_version=version)
