"""HTTP surface tests: what the browser actually calls."""

from __future__ import annotations

from conftest import UNKNOWN_NUMBER, auth


def test_health(client) -> None:
    payload = client.get("/api/health").json()
    assert payload["ok"] is True
    assert payload["payments_mode"] in {"SIMULATED", "SANDBOX", "LIVE"}
    assert payload["audit_ok"] is True


def test_unknown_caller_gets_no_actions(client) -> None:
    start = client.post("/api/calls/start", json={"caller_number": UNKNOWN_NUMBER}).json()
    assert start["verified"] is False
    turn = client.post(f"/api/calls/{start['call_id']}/turn", json={"text": "bijli ka bill bharna hai"}).json()
    assert turn["txn"] is None
    assert "family se juda nahi" in start["greeting"]


def test_dtmf_maps_to_yes_and_no(client) -> None:
    start = client.post("/api/calls/start", json={"caller_number": "9812345678"}).json()
    client.post(f"/api/calls/{start['call_id']}/turn", json={"text": "bijli ka bill bharna hai"})
    yes = client.post(f"/api/calls/{start['call_id']}/dtmf", json={"key": "1"}).json()
    assert yes["decision"] == "AUTO_EXECUTE"
    assert yes["txn"]["state"] == "SUCCEEDED"


def test_console_requires_a_valid_token(client) -> None:
    assert client.get("/api/console/bootstrap").status_code == 401
    assert client.get("/api/console/bootstrap", headers=auth("nonsense")).status_code == 401
    payload = client.get("/api/console/bootstrap", headers=auth()).json()
    assert payload["family"]["id"] == "fam_devi"
    assert payload["limits"]["monthly_cap_paise"] == 500000
    assert payload["modes"]["payments"] == "SIMULATED"
    assert payload["audit"]["ok"] is True


def test_trace_endpoint_returns_policy_rule(client) -> None:
    start = client.post("/api/calls/start", json={"caller_number": "9812345678"}).json()
    turn = client.post(
        f"/api/calls/{start['call_id']}/turn", json={"text": "bijli ka bill bharna hai"}
    ).json()
    assert turn["trace"]["policy"]["rule"] == "P-OK"
    assert turn["trace"]["resolved"]["amount_paise"] == 124000

    trace = client.get(f"/api/calls/{start['call_id']}/trace", headers=auth()).json()
    assert trace["turns"][0]["proposal"]["intent"] == "pay_bill"
    assert trace["audit"]["ok"] is True


def test_pause_endpoint_and_bootstrap_reflect_it(client) -> None:
    paused = client.post("/api/console/pause", json={"paused": True}, headers=auth()).json()
    assert paused["paused"] is True
    bootstrap = client.get("/api/console/bootstrap", headers=auth()).json()
    assert bootstrap["limits"]["paused"] is True
    client.post("/api/console/pause", json={"paused": False}, headers=auth())


def test_child_voice_approval(client) -> None:
    start = client.post("/api/calls/start", json={"caller_number": "9812345678"}).json()
    turn = client.post(
        f"/api/calls/{start['call_id']}/turn", json={"text": "paani ka bill bharna hai"}
    ).json()
    approval_id = turn["approval"]["id"]
    decided = client.post(
        f"/api/console/approvals/{approval_id}/voice", json={"text": "haan kar do"}, headers=auth()
    ).json()
    assert decided["status"] == "approved"


def test_demo_reset(client) -> None:
    response = client.post("/api/demo/reset")
    assert response.status_code == 200
    assert response.json()["ok"] is True
