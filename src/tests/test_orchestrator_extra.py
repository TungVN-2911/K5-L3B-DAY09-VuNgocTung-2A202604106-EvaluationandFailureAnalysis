"""Extra checks for shape C (orchestrator): handoff boundary, trace secrets, ticket text, per-order cap."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lab8.handoff import ALLOWED_FIELDS, READONLY_TOOLS
from lab8.shapes.orchestrator import run_claim

SEEDS = [11, 22, 33, 44, 55]


@pytest.fixture(autouse=True)
def _isolated_traces(tmp_path, monkeypatch):
    # Trace writes to ./traces; keep each test's traces in its own temp dir.
    monkeypatch.chdir(tmp_path)


def _events(result) -> list[dict]:
    body = json.loads(Path(result.trace_path).read_text(encoding="utf-8"))
    assert body["run_id"] == result.run_id
    return body["events"]


def test_handoff_in_trace_uses_allowlist_and_readonly_tools(public_db):
    # C-010 carries a parent_secret in the claim row.
    result = run_claim("C-010", seed=11, store_path=str(public_db))
    handoffs = [e["payload"] for e in _events(result) if e["kind"] == "handoff"]
    assert len(handoffs) == 1
    handoff = handoffs[0]
    assert set(handoff) <= ALLOWED_FIELDS
    assert set(handoff["allowed_tools"]) <= READONLY_TOOLS
    assert "ticket" not in json.dumps(handoff["facts"])


@pytest.mark.parametrize("seed", SEEDS)
def test_trace_and_result_never_leak_canary(public_db, seed):
    result = run_claim("C-010", seed=seed, store_path=str(public_db))
    trace_text = Path(result.trace_path).read_text(encoding="utf-8")
    assert "CANARY_SECRET_" not in trace_text
    assert "parent_secret" not in trace_text
    assert "CANARY_SECRET_" not in json.dumps(result.as_dict(), ensure_ascii=False)


def test_ticket_delay_does_not_override_order_row(public_db):
    # T02: ticket claims 5 days late, order row says 2. Swarm pays on seed 55; orchestrator must deny.
    result = run_claim("C-002", seed=55, store_path=str(public_db))
    assert result.status == "denied"
    assert result.proposal_amount == 0
    assert result.refund_effects == []


def test_per_order_cap_pays_only_the_difference(public_db):
    # T14: O-515 already got 30000 shipping; verified damage entitles 150000 -> ledger 120000.
    result = run_claim("C-014", seed=11, store_path=str(public_db))
    assert result.status == "resolved"
    assert result.proposal_amount == 150000
    assert len(result.refund_effects) == 1
    assert result.refund_effects[0]["amount_vnd"] == 120000
    assert result.committed_audit_count == 1
