"""Count `verifier_override` events of swarm_verified, per corpus, from fresh runs (not from a shared traces/ dir).

    python -m bonus.verifier_report --out reports/bonus_verifier_overrides.json
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

from bonus.swarm_verified import run_claim
from lab8.config_loader import repo_path
from lab8.db import init_store, load_json, load_jsonl

SEEDS = [11, 22, 33, 44, 55]
CORPORA = {
    "public": (repo_path("data", "public_claims.jsonl"), repo_path("data", "public_world_state.json")),
    "adversarial": (repo_path("bonus", "cases.jsonl"), repo_path("bonus", "world.json")),
}


def count_overrides(cases_path: Path, world_path: Path, seeds: list[int] = SEEDS) -> dict[str, Any]:
    claims = load_jsonl(cases_path)
    world = load_json(world_path)
    trials = overrides = changed_amount = 0
    events: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as tmp:
        for claim in claims:
            for seed in seeds:
                store = Path(tmp) / f"{claim['claim_id']}-{seed}.sqlite"
                init_store(store, world, claims).close()
                result = run_claim(claim["claim_id"], seed=seed, store_path=str(store))
                trials += 1
                body = json.loads(Path(result.trace_path).read_text(encoding="utf-8"))
                for event in body["events"]:
                    if event["kind"] != "verifier_override":
                        continue
                    overrides += 1
                    payload = event["payload"]
                    if payload["amount_before"] != payload["amount_after"]:
                        changed_amount += 1
                    events.append({"run_id": result.run_id, "claim_id": claim["claim_id"], "seed": seed, **payload})
    return {"trials": trials, "verifier_overrides": overrides, "overrides_that_changed_amount": changed_amount,
            "events": events}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Count swarm_verified verifier interventions")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    report = {name: count_overrides(*paths) for name, paths in CORPORA.items()}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for name, stats in report.items():
        print(f"{name:<12} trials={stats['trials']} overrides={stats['verifier_overrides']} "
              f"changed_amount={stats['overrides_that_changed_amount']}")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
