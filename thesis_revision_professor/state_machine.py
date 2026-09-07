"""Stable issue lifecycle and convergence tracking for multi-round revision."""

from __future__ import annotations

from datetime import datetime, timezone

from .review_engine import issue_fingerprint, legacy_fingerprint


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


def _identity_keys(item: dict) -> list[str]:
    """All fingerprints under which a stored issue may be known.

    Older states used wording-dependent fingerprints; newer ones use
    rule_id|locator. Recompute both so either generation matches.
    """
    keys = []
    stored = item.get("fingerprint") or item.get("id")
    if stored:
        keys.append(stored)
    rule_id = str(item.get("rule_id", ""))
    locator = str(item.get("locator", ""))
    if rule_id and locator:
        keys.append(issue_fingerprint(rule_id, locator))
        keys.append(legacy_fingerprint(rule_id, locator, str(item.get("finding", ""))))
    return keys


def _normalize_fingerprint(item: dict) -> dict:
    """Rewrite an issue onto the current (wording-independent) fingerprint."""
    item = dict(item)
    rule_id = str(item.get("rule_id", ""))
    locator = str(item.get("locator", ""))
    if rule_id and locator:
        item["fingerprint"] = issue_fingerprint(rule_id, locator)
    return item


def advance_state(previous: dict | None, payload: dict, *, phase: str) -> dict:
    state = dict(previous or initial_state())
    prior_items = [dict(item) for item in _legacy_issues(state)]
    prior_by_key: dict[str, dict] = {}
    for item in prior_items:
        for key in _identity_keys(item):
            prior_by_key.setdefault(key, item)
    current = {}
    matched_prior: set[str] = set()
    new_risks = []
    for item in payload.get("review", {}).get("issues", []):
        key = item.get("fingerprint", item.get("id"))
        value = _normalize_fingerprint(item)
        value_key = value.get("fingerprint", key)
        prior_item = prior_by_key.get(key) or prior_by_key.get(value_key)
        if prior_item is not None:
            matched_prior.add(prior_item.get("fingerprint", prior_item.get("id")))
            prior_status = prior_item.get("status", "open")
            if prior_status in {"resolved", "waived"}:
                value["status"] = "reopened"
            elif prior_status == "applied":
                # 已应用的修改在本轮 findings 中再次出现：修改未生效或被回改。
                value["status"] = "regressed"
            else:
                value["status"] = prior_status
        else:
            value["status"] = "open"
            if value.get("priority") in {"P0", "P1"}:
                new_risks.append(value)
        current[value_key] = value
    resolved = [_normalize_fingerprint(item) for item in state.get("resolved", [])]
    resolved_keys = {item.get("fingerprint", item.get("id")) for item in resolved}
    for item in prior_items:
        identity = item.get("fingerprint", item.get("id"))
        if identity in matched_prior or identity in current or identity in resolved_keys:
            continue
        if item.get("status", "open") in ACTIVE:
            value = _normalize_fingerprint(item)
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
