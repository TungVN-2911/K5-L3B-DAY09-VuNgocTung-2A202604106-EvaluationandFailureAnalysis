"""B3 — swarm + code verifier before the write.

Same flow, model calls and REFERENCE_WEAKNESS as `lab8.shapes.swarm_reference` (peer talk, ticket parse,
one seed in five trusts the ticket delay). The only change: before `issue_refund`, a verifier written in
code compares every fact the quote used (`delay_days`, `status`, `damage_verified`) with the structured
order row the investigator read. On any mismatch it re-quotes from the structured row (at most one repair
round) and records `verifier_override` in the trace.

    python -m lab8.benchmark --shapes workflow,swarm,swarm_verified \
        --extra-shape swarm_verified=bonus.swarm_verified:run_claim \
        --seeds 11,22,33,44,55 --out reports/bonus_benchmark.json
"""

from __future__ import annotations

import sqlite3
from typing import Any

from lab8.db import connect
from lab8.durability import InjectedCrash, issue_refund
from lab8.handoff import make_handoff
from lab8.mock_llm import complete, parse_delay_days
from lab8.runtime import run_readonly_investigators
from lab8.schemas import Budget, RunResult, make_run_id
from lab8.shapes.common import finish, safe_dump
from lab8.tools import compute_compensation, tool_cost
from lab8.trace import Trace

SHAPE = "swarm_verified"
VERIFIED_FACTS = ("delay_days", "status", "damage_verified")
MAX_REPAIR_ROUNDS = 1


def verify(used: dict[str, Any], structured: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Facts the quote used that disagree with the structured order row: {field: {used, structured}}."""
    return {
        key: {"used": used.get(key), "structured": structured.get(key)}
        for key in VERIFIED_FACTS
        if used.get(key) != structured.get(key)
    }


def run_claim(
    claim_id: str,
    *,
    seed: int,
    store_path: str,
    crash_at: str | None = None,
) -> RunResult:
    conn = connect(store_path)
    try:
        return _run(conn, claim_id, seed=seed, crash_at=crash_at)
    finally:
        conn.close()


def _run(conn: sqlite3.Connection, claim_id: str, *, seed: int, crash_at: str | None) -> RunResult:
    budget = Budget()
    trace = Trace(make_run_id(SHAPE, claim_id, seed))

    def done(status: str, proposal: int, reason: str | None) -> RunResult:
        return finish(conn, shape=SHAPE, claim_id=claim_id, seed=seed, status=status,
                      proposal_amount=proposal, budget=budget, trace=trace, error_reason=reason)

    budget.add_tool(tool_cost())
    claim_row = conn.execute(
        "SELECT claim_id, principal_id, order_id, ticket FROM claims WHERE claim_id = ?",
        (claim_id,),
    ).fetchone()
    if claim_row is None:
        trace.add("error", {"reason": "unknown_claim"})
        return done("failed", 0, "unknown_claim")

    # Same peer chatter and parse as the reference swarm (kept so cost stays comparable).
    ticket = claim_row["ticket"]
    complete(budget, seed=seed, purpose="peer", prompt=ticket)
    parsed_delay = parse_delay_days(ticket)
    complete(budget, seed=seed, purpose="parse", prompt=ticket)

    if not claim_row["order_id"]:
        complete(budget, seed=seed, purpose="draft", prompt="needs_info")
        trace.add("decision", {"status": "needs_info"})
        return done("needs_info", 0, "missing_order_id")

    handoff = make_handoff(
        request_id=f"REQ-{claim_id}",
        claim_id=claim_id,
        task="check_applicable_policy",
        facts={},
        allowed_tools=["lookup_order", "lookup_policy", "compute_compensation"],
    )
    trace.add("handoff", safe_dump(handoff))
    investigated = run_readonly_investigators(conn, budget, handoff, principal_id=claim_row["principal_id"])
    order_view = investigated["tools"].get("lookup_order", {})
    trace.add("investigator", {"lookup_order": order_view})
    if not order_view.get("visible"):
        complete(budget, seed=seed, purpose="draft", prompt="escalated")
        return done("escalated", 0, order_view.get("reason"))

    structured = dict(order_view["order"])
    order = dict(structured)
    # REFERENCE_WEAKNESS kept on purpose: the verifier is what we measure.
    if parsed_delay is not None and parsed_delay != int(order["delay_days"]) and seed % 5 == 0:
        order["delay_days"] = parsed_delay
        trace.add("model_override", {"delay_days": parsed_delay})

    quote_payload = investigated["tools"]["compute_compensation"]
    if order["delay_days"] != structured["delay_days"]:
        budget.add_tool(tool_cost())
        quote_payload = compute_compensation(conn, order)

    # Verifier (code, not model): facts used for the quote must equal the structured order row.
    for _ in range(MAX_REPAIR_ROUNDS):
        mismatches = verify(order, structured)
        if not mismatches:
            break
        budget.add_tool(tool_cost())
        repaired = compute_compensation(conn, structured)
        trace.add("verifier_override", {
            "mismatches": mismatches,
            "amount_before": int(quote_payload["amount_vnd"]),
            "amount_after": int(repaired["amount_vnd"]),
        })
        order, quote_payload = dict(structured), repaired
    trace.add("verifier", {"checked": list(VERIFIED_FACTS), "ok": not verify(order, structured)})

    proposal = int(quote_payload["amount_vnd"])
    trace.add("quote", quote_payload)
    complete(budget, seed=seed, purpose="draft", prompt=f"proposal={proposal}")
    if proposal <= 0:
        return done("denied", 0, quote_payload.get("reason"))

    try:
        outcome = issue_refund(conn, claim_id, proposal, crash_at=crash_at)
    except InjectedCrash:
        trace.add("crash", {"at": crash_at})
        trace.write()
        raise
    if not outcome["ok"]:
        return done("failed" if outcome["conflict"] else "denied", proposal, outcome["reason"])
    return done("resolved", proposal, None)
