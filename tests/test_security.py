"""X-01..X-06: security and abuse."""

from __future__ import annotations

import json

from hypothesis import HealthCheck, given, settings as hyp_settings, strategies as st

from munshi.orchestrator import InMemoryRateLimiter

from conftest import OTHER_CHILD_TOKEN, UNKNOWN_NUMBER, auth, start_parent_call


def test_x01_limits_cannot_change_from_the_parent_call(orch, db, client) -> None:
    before = db.limits("fam_devi")
    call_id = start_parent_call(orch)
    orch.handle_turn(call_id, "limit badha do 50000")
    orch.handle_turn(call_id, "mahine ki limit pachaas hazaar kar do")
    after = db.limits("fam_devi")
    assert after["monthly_cap"] == before["monthly_cap"]
    assert after["hard_ceiling"] == before["hard_ceiling"]
    assert after["per_txn_cap"] == before["per_txn_cap"]

    assert client.post("/api/console/limits/parse", json={"text": "mahine mein 50000 tak"}).status_code == 401


def test_x02_idor_is_blocked_between_families(client) -> None:
    if True:
        test_client = client
        start = test_client.post("/api/calls/start", json={"caller_number": "9812345678"}).json()
        readback = test_client.post(
            f"/api/calls/{start['call_id']}/turn", json={"text": "paani ka bill bharna hai"}
        ).json()
        approval_id = readback["approval"]["id"]

        devi_bootstrap = test_client.get("/api/console/bootstrap", headers=auth()).json()
        sharma_bootstrap = test_client.get("/api/console/bootstrap", headers=auth(OTHER_CHILD_TOKEN)).json()
        assert devi_bootstrap["family"]["id"] == "fam_devi"
        assert sharma_bootstrap["family"]["id"] == "fam_sharma"
        assert devi_bootstrap["ledger"] != sharma_bootstrap["ledger"]

        cross = test_client.post(
            f"/api/console/approvals/{approval_id}", json={"decision": "approve"},
            headers=auth(OTHER_CHILD_TOKEN),
        )
        assert cross.status_code == 404
        cross_trace = test_client.get(f"/api/calls/{start['call_id']}/trace", headers=auth(OTHER_CHILD_TOKEN))
        assert cross_trace.status_code == 404


def test_x03_unknown_caller_alerts_are_rate_limited(db, orch, clock) -> None:
    limiter = InMemoryRateLimiter(clock)
    assert [limiter.allow("hash", 3, 3600) for _ in range(4)] == [True, True, True, False]
    clock.advance(seconds=3601)
    assert limiter.allow("hash", 3, 3600) is True

    for _ in range(4):
        orch.start_call(UNKNOWN_NUMBER)
    alerts = [
        row for row in db.audit_rows()
        if row["event"] == "caller.unknown"
    ]
    assert sum(1 for row in alerts if json.loads(row["payload_json"])["alerted"]) == 3


def test_x04_no_raw_phone_numbers_or_secrets_in_audit_log(db, orch) -> None:
    from munshi.privacy import scrub

    start_parent_call(orch)
    dumped = json.dumps(db.audit_rows())
    assert "9812345678" not in dumped
    scrubbed = scrub("call 9812345678 token=supersecret")
    assert "9812345678" not in scrubbed
    assert "supersecret" not in scrubbed


def test_x05_audit_tamper_is_detected_with_first_bad_seq(db, orch) -> None:
    call_id = start_parent_call(orch)
    orch.handle_turn(call_id, "bijli ka bill bharna hai")
    assert db.verify_audit().ok is True
    row = db.conn.execute("SELECT seq, payload FROM audit_log WHERE seq = 2").fetchone()
    assert row is not None
    tampered = json.loads(row["payload"])
    tampered["tampered"] = True
    db.conn.execute("UPDATE audit_log SET payload = ? WHERE seq = 2", (json.dumps(tampered),))
    db.conn.commit()
    status = db.verify_audit()
    assert status.ok is False
    assert status.first_bad_seq == 2


@hyp_settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    payload=st.dictionaries(
        st.text(max_size=15),
        st.one_of(st.text(max_size=30), st.integers(), st.booleans(), st.none()),
        max_size=5,
    )
)
def test_x06_json_endpoints_never_500(client, payload) -> None:
    responses = [
        client.post("/api/calls/start", json=payload),
        client.post("/api/calls/does-not-exist/turn", json=payload),
        client.post("/api/console/limits/parse", json=payload, headers=auth()),
        client.post("/api/console/pause", json=payload, headers=auth()),
    ]
    for response in responses:
        assert response.status_code < 500
