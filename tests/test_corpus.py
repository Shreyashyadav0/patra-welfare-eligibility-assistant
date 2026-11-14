"""Corpus integrity: every criterion must quote its document exactly."""
from pathlib import Path

from patra.corpus import load_corpus
from patra.settings import CORPUS_DIR, CRITERIA_DIR

corpus = load_corpus(CORPUS_DIR, CRITERIA_DIR)


def test_schemes_and_criteria_loaded():
    assert len(corpus.schemes) >= 6
    assert sum(len(s.criteria) for s in corpus.schemes.values()) >= 15


def test_every_clause_span_resolves_to_its_own_text():
    for scheme in corpus.schemes.values():
        for c in scheme.criteria:
            text = corpus.documents[c.doc_id].text
            assert text[c.span_start:c.span_end] == c.clause_text


def test_span_is_not_in_a_different_document():
    for scheme in corpus.schemes.values():
        for c in scheme.criteria:
            assert c.doc_id in corpus.documents


def test_corpus_version_is_stable():
    again = load_corpus(CORPUS_DIR, CRITERIA_DIR)
    assert again.corpus_version == corpus.corpus_version


def test_chunks_have_offsets():
    for chunk in corpus.chunks[:20]:
        doc = corpus.documents[chunk.doc_id]
        assert doc.text[chunk.span_start:chunk.span_end].strip() == chunk.text
