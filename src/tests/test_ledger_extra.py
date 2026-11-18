"""Shape-level ledger checks: crash at every point, broken approvals. Add shapes to SHAPES_UNDER_TEST as they land."""

from __future__ import annotations

import pytest

from lab8.db import connect
from lab8.durability import InjectedCrash
from lab8.shapes import SHAPES

SHAPES_UNDER_TEST = ["orchestrator", "workflow", "single"]
CRASH_POINTS = ["before_effect", "after_effect_before_checkpoint", "after_checkpoint"]


@pytest.fixture(autouse=True)
def _isolated_traces(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def _ledger_rows(store, claim_id: str) -> int:
    conn = connect(store)
    try:
        return conn.execute("SELECT COUNT(*) AS n FROM refund_ledger WHERE claim_id = ?", (claim_id,)).fetchone()["n"]
    finally:
        conn.close()


def _denials(store, claim_id: str) -> list[str]:
    conn = connect(store)
    try:
        rows = conn.execute(
            "SELECT details_json FROM audit_events WHERE claim_id = ? AND event_type = 'policy_denied'",
            (claim_id,),
        ).fetchall()
        return [row["details_json"] for row in rows]
    finally:
        conn.close()


def _mutate(store, sql: str) -> None:
    conn = connect(store)
    try:
        conn.execute(sql)
        conn.commit()
    finally:
        conn.close()


@pytest.mark.parametrize("shape", SHAPES_UNDER_TEST)
@pytest.mark.parametrize("point", CRASH_POINTS)
def test_crash_then_resume_pays_once(public_db, shape, point):
    with pytest.raises(InjectedCrash):
        SHAPES[shape]("C-001", seed=11, store_path=str(public_db), crash_at=point)
    result = SHAPES[shape]("C-001", seed=11, store_path=str(public_db))
    assert result.status == "resolved"
    assert result.proposal_amount == 35000
    assert _ledger_rows(public_db, "C-001") == 1
    assert result.committed_audit_count == 1


BROKEN_APPROVALS = {
    "revoked": "UPDATE approvals SET status = 'revoked' WHERE approval_id = 'A-001'",
    "other_claim": "UPDATE approvals SET claim_id = 'C-999' WHERE approval_id = 'A-001'",
    "missing": "UPDATE claims SET approval_id = NULL WHERE claim_id = 'C-001'",
}


@pytest.mark.parametrize("shape", SHAPES_UNDER_TEST)
@pytest.mark.parametrize("case", sorted(BROKEN_APPROVALS))
def test_broken_approval_denies_with_audit(public_db, shape, case):
    _mutate(public_db, BROKEN_APPROVALS[case])
    result = SHAPES[shape]("C-001", seed=11, store_path=str(public_db))
    assert result.status == "denied"
    assert result.proposal_amount == 35000  # full quote, host refused
    assert result.refund_effects == []
    assert _ledger_rows(public_db, "C-001") == 0
    denials = _denials(public_db, "C-001")
    assert denials, "quote > 0 refused by host must leave a policy_denied audit"
    if case == "other_claim":
        assert any("approval_claim_mismatch" in d for d in denials)


@pytest.mark.parametrize("shape", SHAPES_UNDER_TEST)
def test_expired_approval_in_public_data_is_denied(public_db, shape):
    # C-007 uses A-007, expired 2020-01-01.
    result = SHAPES[shape]("C-007", seed=11, store_path=str(public_db))
    assert result.status == "denied"
    assert result.refund_effects == []
    assert _ledger_rows(public_db, "C-007") == 0
