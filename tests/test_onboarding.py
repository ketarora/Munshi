"""O-01..O-04: onboarding by voice note."""

from __future__ import annotations

import pytest

from munshi.errors import SecondFactorRequired
from munshi.limits import parse_limits_note

from conftest import auth


def test_o01_hindi_number_words_are_not_confused() -> None:
    fifty_thousand = parse_limits_note("mahine mein pachaas hazaar tak")
    assert fifty_thousand.monthly_rupees == 50000
    five_thousand = parse_limits_note("mahine mein paanch hazaar tak")
    assert five_thousand.monthly_rupees == 5000
    digits = parse_limits_note("bijli ke liye mahine mein 5,000 tak")
    assert digits.monthly_rupees == 5000


def test_o02_nothing_saves_without_readback_and_explicit_confirmation(client) -> None:
    before = client.get("/api/console/bootstrap", headers=auth()).json()["limits"]
    parsed = client.post(
        "/api/console/limits/parse",
        json={"text": "Amma ke liye bijli, gas aur dawai, mahine mein 5,000 tak."},
        headers=auth(),
    ).json()
    assert parsed["saved"] is False
    assert parsed["token"]
    assert "Mahine mein 5,000 rupaye tak" in parsed["parsed"]["readback"]

    unchanged = client.get("/api/console/bootstrap", headers=auth()).json()["limits"]
    assert unchanged["monthly_cap_paise"] == before["monthly_cap_paise"]

    decline = client.post(
        "/api/console/limits/confirm", json={"token": parsed["token"], "confirmed": False}, headers=auth()
    ).json()
    assert decline["saved"] is False
    still = client.get("/api/console/bootstrap", headers=auth()).json()["limits"]
    assert still["monthly_cap_paise"] == before["monthly_cap_paise"]


def test_o03_contradictory_limits_ask_instead_of_guessing(client) -> None:
    parsed = client.post(
        "/api/console/limits/parse",
        json={"text": "bijli ke liye mahine mein 5000 tak, lekin ek baar mein 8000"},
        headers=auth(),
    ).json()
    assert parsed["saved"] is False
    assert parsed["token"] is None
    assert parsed["parsed"]["needs_clarification"] is True


def test_o04_limit_increase_needs_a_second_factor(client, orch) -> None:
    parsed = client.post(
        "/api/console/limits/parse",
        json={"text": "bijli ke liye mahine mein 8,000 tak"},
        headers=auth(),
    ).json()
    assert parsed["requires_second_factor"] is True

    with pytest.raises(SecondFactorRequired):
        orch.confirm_limits("fam_devi", parsed["token"], confirmed=True)

    saved = orch.confirm_limits("fam_devi", parsed["token"], confirmed=True, second_factor="246810")
    assert saved["saved"] is True
    assert saved["limits"]["monthly_cap_paise"] == 800000
    assert orch.db.limits("fam_devi")["monthly_cap"] == 800000


def test_o05_decrease_needs_no_second_factor(client, orch) -> None:
    parsed = client.post(
        "/api/console/limits/parse",
        json={"text": "bijli ke liye mahine mein 3,000 tak"},
        headers=auth(),
    ).json()
    assert parsed["requires_second_factor"] is False
    saved = orch.confirm_limits("fam_devi", parsed["token"], confirmed=True)
    assert saved["limits"]["monthly_cap_paise"] == 300000
