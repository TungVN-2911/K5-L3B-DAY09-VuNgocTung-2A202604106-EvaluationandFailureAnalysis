"""Student custom test cases for workflow (Shape A) and single agent (Shape B).

Demonstrates test additions for the contribution rubric (C8 in RUBRIC.md and TEAM.md).
"""

from __future__ import annotations

import pytest

from lab8.db import init_store
from lab8.shapes.single import run_claim as run_single
from lab8.shapes.workflow import run_claim as run_workflow
from tests.conftest import CLAIMS, WORLD


def _init_test_store(tmp_path, name: str):
    path = tmp_path / name
    init_store(path, WORLD, CLAIMS).close()
    return path


def test_workflow_missing_order_id_triggers_needs_info(tmp_path):
    """Test that workflow shape correctly identifies missing order_id and returns needs_info without ledger writes."""
    store_path = _init_test_store(tmp_path, "wf_missing_order.sqlite")
    # C-004 has None/missing order_id in standard dataset
    result = run_workflow("C-004", seed=11, store_path=str(store_path))
    assert result.status == "needs_info"
    assert result.proposal_amount == 0
    assert result.error_reason == "missing_order_id"
    assert len(result.refund_effects) == 0


def test_workflow_escalation_for_unauthorized_order(tmp_path):
    """Test that workflow shape safely escalates when principal does not own the order."""
    store_path = _init_test_store(tmp_path, "wf_escalated.sqlite")
    # C-005 tests unauthorized order ownership
    result = run_workflow("C-005", seed=11, store_path=str(store_path))
    assert result.status == "escalated"
    assert result.proposal_amount == 0
    assert len(result.refund_effects) == 0


def test_single_react_agent_denied_below_threshold(tmp_path):
    """Test that single ReAct agent properly denies claims with delay < 3 days."""
    store_path = _init_test_store(tmp_path, "single_denied.sqlite")
    # C-002 has 2 days delay, less than 3-day policy requirement
    result = run_single("C-002", seed=11, store_path=str(store_path))
    assert result.status == "denied"
    assert result.proposal_amount == 0
    assert len(result.refund_effects) == 0


def test_single_react_agent_successful_refund(tmp_path):
    """Test that single ReAct agent runs tools, computes refund and successfully records one ledger effect."""
    store_path = _init_test_store(tmp_path, "single_resolved.sqlite")
    # C-001 is a clean eligible claim with 35,000 VND refund
    result = run_single("C-001", seed=11, store_path=str(store_path))
    assert result.status == "resolved"
    assert result.proposal_amount == 35000
    assert len(result.refund_effects) == 1
    assert result.refund_effects[0]["amount_vnd"] == 35000
    assert result.tool_calls >= 2  # ReAct agent called lookup_order and compute_compensation
