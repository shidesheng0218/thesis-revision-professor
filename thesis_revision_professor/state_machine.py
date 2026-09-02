"""Stable issue lifecycle and convergence tracking for multi-round revision."""

from __future__ import annotations

from datetime import datetime, timezone


ACTIVE = {"open", "confirmed", "applied", "reopened", "blocked", "regressed"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def initial_state() -> dict:
    return {
        "schema_version": "4.0",
        "created_at": _now(),
        "updated_at": _now(),
        "round": 0,
        "max_rounds": 5,
        "status": "initialized",
        "phase": "baseline_scan",
        "source_hash": None,
        "issues": [],
        "resolved": [],
        "new_risks": [],
        "confirmation_queue": [],
        "strategy_matches": [],
        "scores": [],
        "deliverables": [],
        "convergence": {},
        "stable_rounds": 0,
        "history": [],
    }


def _legacy_issues(state: dict) -> list[dict]:
    if state.get("issues"):
        return state["issues"]
    return [item for bucket in ("p0", "p1", "p2") for item in state.get(bucket, [])]


def advance_state(previous: dict | None, payload: dict, *, phase: str) -> dict:
    state = dict(previous or initial_state())
    prior = {item.get("fingerprint", item.get("id")): dict(item) for item in _legacy_issues(state)}
    current = {}
    new_risks = []
    for item in payload.get("review", {}).get("issues", []):
        key = item.get("fingerprint", item.get("id"))
        value = dict(item)
        if key in prior and prior[key].get("status") in {"resolved", "waived"}:
            value["status"] = "reopened"
        elif key in prior:
            value["status"] = prior[key].get("status", "open")
        else:
            value["status"] = "open"
            if value.get("priority") in {"P0", "P1"}:
                new_risks.append(value)
        current[key] = value
    resolved = list(state.get("resolved", []))
    resolved_keys = {item.get("fingerprint", item.get("id")) for item in resolved}
    for key, item in prior.items():
        if key not in current and item.get("status", "open") in ACTIVE and key not in resolved_keys:
            value = dict(item)
            value["status"] = "resolved"
            value["resolved_at"] = _now()
            resolved.append(value)
    issues = list(current.values())
    confirmation_queue = [item for item in payload.get("revision_plan", {}).get("items", []) if item.get("requires_author_confirmation") and not item.get("confirmed")]
    scores = list(state.get("scores", []))
    if payload.get("rubric"):
        scores.append(payload["rubric"])
    prior_average = scores[-2].get("average") if len(scores) >= 2 else None
    current_average = scores[-1].get("average") if scores else None
    score_delta = None if prior_average is None or current_average is None else round(current_average - prior_average, 3)
    stable_rounds = int(state.get("stable_rounds", 0))
    if not new_risks and score_delta is not None and abs(score_delta) < 0.05:
        stable_rounds += 1
    else:
        stable_rounds = 0
    convergence = payload.get("convergence", {})
    all_gates = bool(convergence) and all(convergence.values())
    next_round = int(state.get("round", 0)) + 1
    if next_round > int(state.get("max_rounds", 5)):
        state_status = "manual_review_required"
        state_phase = "manual_review"
    else:
        state_status = "complete" if all_gates else "in_progress"
        state_phase = "word_export" if all_gates else phase
    state.update(
        {
            "schema_version": "4.0",
            "updated_at": _now(),
            "round": next_round,
            "status": state_status,
            "phase": state_phase,
            "source_hash": payload.get("source_hash"),
            "issues": issues,
            "p0": [item for item in issues if item.get("priority") == "P0" and item.get("status") in ACTIVE],
            "p1": [item for item in issues if item.get("priority") == "P1" and item.get("status") in ACTIVE],
            "p2": [item for item in issues if item.get("priority") == "P2" and item.get("status") in ACTIVE],
            "resolved": resolved,
            "new_risks": new_risks,
            "confirmation_queue": confirmation_queue,
            "strategy_matches": [payload.get("strategy", {})],
            "scores": scores,
            "deliverables": payload.get("deliverables", []),
            "convergence": convergence,
            "stable_rounds": stable_rounds,
        }
    )
    history = list(state.get("history", []))
    history.append(
        {
            "round": state["round"],
            "created_at": _now(),
            "phase": phase,
            "source_hash": payload.get("source_hash"),
            "issue_counts": {priority: sum(item.get("priority") == priority for item in issues) for priority in ("P0", "P1", "P2")},
            "new_risk_count": len(new_risks),
            "resolved_count": len(resolved),
            "score_delta": score_delta,
            "regression": payload.get("regression", {}).get("regression_result"),
        }
    )
    state["history"] = history
    return state
