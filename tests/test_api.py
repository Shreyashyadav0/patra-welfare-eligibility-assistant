from fastapi.testclient import TestClient

from patra.api import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["schemes"] >= 6


def test_schemes_list():
    r = client.get("/schemes")
    assert r.status_code == 200
    assert any(s["scheme_id"] == "pmkisan" for s in r.json())


def test_query_returns_verdict_and_citations():
    r = client.post("/query", json={
        "question": "I am a 45 year old farmer who does not pay income tax. Am I eligible for PM-KISAN?",
        "profile": {"occupation": "farmer", "age": 45, "income_tax_payer": "no", "govt_employee": "no"},
    })
    assert r.status_code == 200
    body = r.json()
    assert body["verdict_type"] == "eligible"
    assert body["citations"], "every verdict must carry citations"


def test_query_rejects_empty_question():
    r = client.post("/query", json={"question": ""})
    assert r.status_code == 422


def test_home_page_renders():
    r = client.get("/")
    assert r.status_code == 200
    assert "Patra" in r.text
