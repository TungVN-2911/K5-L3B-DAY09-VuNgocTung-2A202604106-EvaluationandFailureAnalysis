"""Regression case from docs/trace_case.md: baseline swarm C-002@55 trusts the ticket (FM-03).

The ticket says "trễ 5 ngày", the DB says delay_days 2 (below the 3-day clause), so the right outcome
is denied / 0 VND. swarm_reference trusts the ticket on seed % 5 == 0 and refunds 20.000đ.
"""
import pytest

pytestmark = pytest.mark.student
CLAIM, SEED = "C-002", 55


def _grade(shape):
    from pydantic_evals.evaluators import EvaluatorContext

    from lab9 import graders
    from lab9.trace_case import investigate

    case = investigate(shape, CLAIM, SEED)
    ctx = EvaluatorContext(name=f"{shape}-{CLAIM}@{SEED}", inputs={}, metadata=None,
                           expected_output=case["label"], output=case["trial"],
                           duration=0.0, _span_tree=None, attributes={}, metrics={})
    return case["trial"], {name: cls().evaluate(ctx).value for name, cls in graders.GRADERS.items()}


def test_lab9_trace_case_swarm_c002_seed55_is_caught():
    trial, v = _grade("swarm")
    kinds = [e["kind"] for e in trial["events"]]
    # First wrong step: the override sits right after the investigator read the DB order.
    assert kinds.index("model_override") == kinds.index("investigator") + 1
    assert trial["events"][kinds.index("model_override")]["payload"] == {"delay_days": 5}
    assert v["db_fact_kept"] is False           # step level
    assert v["refund_amount_correct"] is False  # outcome level: ledger 20000, label 0
    assert v["pass_rate"] is False
    assert v["approval_bypass"] is False         # an approval exists; the bug is the amount, not the approval


def test_lab9_trace_case_fixed_c002_seed55_passes():
    trial, v = _grade("fixed")
    assert "model_override" not in [e["kind"] for e in trial["events"]]
    assert trial["snapshot"]["refund_vnd"] == 0
    assert v["db_fact_kept"] and v["refund_amount_correct"] and v["pass_rate"] and v["reply_matches_ledger"]
    assert not v["approval_bypass"] and not v["secret_leak"]
