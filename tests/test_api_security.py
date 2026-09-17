"""API-layer input-validation regressions, added by the pre-deployment
audit (2026-09-17). Confirms invalid input returns a proper 4xx instead
of an unhandled 500, and that basic path/lookup parameters can't be used
to reach data outside the intended session/fixture namespace."""
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200


def test_unknown_fixture_is_404_not_500():
    resp = client.get("/api/fixtures/does-not-exist")
    assert resp.status_code == 404


def test_submit_session_with_invalid_tool_is_400_not_500():
    resp = client.post("/api/sessions", json={
        "session_id": "bad-tool-session",
        "calls": [{"tool": "delete_everything", "resource_id": "x"}],
    })
    assert resp.status_code == 400
    assert "delete_everything" in resp.json()["detail"] or "Unknown tool" in resp.json()["detail"]


def test_evaluate_unknown_session_is_404_not_500():
    resp = client.post("/api/sessions/does-not-exist/evaluate")
    assert resp.status_code == 404


def test_evaluate_unknown_system_is_400_not_500():
    resp = client.post("/api/sessions/benign-standard-00/evaluate?system=NotARealSystem")
    assert resp.status_code == 400


def test_evaluate_unknown_policy_variant_is_400_not_500():
    resp = client.post(
        "/api/sessions/benign-standard-00/evaluate?policy_variant=NotARealVariant"
    )
    assert resp.status_code == 400


def test_evaluate_known_attack_fixture_still_blocks():
    resp = client.post(
        "/api/sessions/attack1-two-vendor-sequential-00/evaluate?system=AgentShield"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["final_decision"] == "BLOCK"
    assert body["matched_conflict_class"] == "vendor_pricing_confidentiality"
