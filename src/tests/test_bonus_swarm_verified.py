"""B3 — swarm_verified: code verifier before the write.

    python -m pytest -q tests/test_bonus_swarm_verified.py
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from bonus.swarm_verified import run_claim as run_verified
from bonus.swarm_verified import verify
from lab8.config_loader import repo_path
from lab8.db import connect, init_store, load_json, load_jsonl
from lab8.durability import InjectedCrash
from lab8.metrics import trial_pass
from lab8.shapes.swarm_reference import run_claim as run_swarm
from tests.conftest import CLAIMS, WORLD

ADV_CLAIMS = load_jsonl(repo_path("bonus", "cases.jsonl"))
ADV_WORLD = load_json(repo_path("bonus", "world.json"))
ADV_BY_ID = {row["claim_id"]: row for row in ADV_CLAIMS}


@pytest.fixture(autouse=True)
def _isolated_traces(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def _store(tmp_path, name, world=WORLD, claims=CLAIMS):
    path = tmp_path / f"{name}.sqlite"
    init_store(path, world, claims).close()
    return str(path)


def _events(result, kind):
    body = json.loads(Path(result.trace_path).read_text(encoding="utf-8"))
    return [e["payload"] for e in body["events"] if e["kind"] == kind]


def _passes(result, expected, store, started_at):
    conn = connect(store)
    try:
        return trial_pass(result.as_dict(), expected, conn, started_at=started_at)
    finally:
        conn.close()


def test_verify_reports_only_fields_that_disagree():
    structured = {"delay_days": 2, "status": "delivered", "damage_verified": False}
    assert verify(dict(structured), structured) == {}
    assert verify({**structured, "delay_days": 5}, structured) == {"delay_days": {"used": 5, "structured": 2}}


def test_public_t02_seed55_swarm_pays_but_verifier_blocks(tmp_path):
    # Swarm trusts "trễ 5 ngày" over the order row (2 days) on seed 55 and pays 20000.
    swarm = run_swarm("C-002", seed=55, store_path=_store(tmp_path, "swarm"))
    assert swarm.status == "resolved"
    verified = run_verified("C-002", seed=55, store_path=_store(tmp_path, "verified"))
    assert verified.status == "denied"
    assert verified.refund_effects == []
    overrides = _events(verified, "verifier_override")
    assert overrides == [{"mismatches": {"delay_days": {"used": 5, "structured": 2}},
                          "amount_before": 20000, "amount_after": 0}]


@pytest.mark.parametrize("claim_id", sorted(ADV_BY_ID))
def test_adversarial_cases_pass_on_seed55(tmp_path, claim_id):
    store = _store(tmp_path, claim_id, ADV_WORLD, ADV_CLAIMS)
    started_at = time.time()
    result = run_verified(claim_id, seed=55, store_path=store)
    passed, reason = _passes(result, ADV_BY_ID[claim_id]["expected"], store, started_at)
    assert passed, reason


def test_override_on_same_side_of_threshold_keeps_amount(tmp_path):
    # C-B06: ticket 9 days, order 4 days -> both eligible; verifier still logs the mismatch.
    result = run_verified("C-B06", seed=55, store_path=_store(tmp_path, "b06", ADV_WORLD, ADV_CLAIMS))
    assert result.status == "resolved" and result.proposal_amount == 35000
    [override] = _events(result, "verifier_override")
    assert override["amount_before"] == override["amount_after"] == 35000


def test_no_override_when_seed_does_not_trigger_the_weakness(tmp_path):
    result = run_verified("C-002", seed=11, store_path=_store(tmp_path, "s11"))
    assert _events(result, "verifier_override") == []
    assert _events(result, "verifier") == [{"checked": ["delay_days", "status", "damage_verified"], "ok": True}]


def test_crash_then_resume_pays_once(tmp_path):
    store = _store(tmp_path, "crash")
    with pytest.raises(InjectedCrash):
        run_verified("C-001", seed=55, store_path=store, crash_at="after_effect_before_checkpoint")
    result = run_verified("C-001", seed=55, store_path=store)
    assert result.status == "resolved"
    assert len(result.refund_effects) == 1
    assert result.committed_audit_count == 1


def test_trace_has_no_secret_or_pii(tmp_path):
    result = run_verified("C-B01", seed=55, store_path=_store(tmp_path, "pii", ADV_WORLD, ADV_CLAIMS))
    text = Path(result.trace_path).read_text(encoding="utf-8")
    for forbidden in ADV_BY_ID["C-B01"]["expected"]["forbid_substrings"]:
        assert forbidden not in text
