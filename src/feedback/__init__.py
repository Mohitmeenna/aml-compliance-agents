"""Alert disposition feedback that changes future screening behaviour."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from src.config import load_settings
from src.paths import FEEDBACK_DIR, UNDERSTANDING_DIR
from src.understanding import build_understanding, load_feedback_adjustments


def _ensure_dirs() -> None:
    FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)


def _dispositions_path() -> Path:
    return FEEDBACK_DIR / "dispositions.jsonl"


def _adjustments_path() -> Path:
    return FEEDBACK_DIR / "score_adjustments.json"


def _few_shot_path() -> Path:
    settings = load_settings()
    return Path(settings["feedback"]["few_shot_memory_path"])


def record_disposition(
    *,
    alert_id: str,
    disposition: str,
    rationale: str,
    actor_user_id: str,
    alert: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    disposition in {true_hit, false_positive, escalate}
    Updates score multipliers and few-shot memory, then rebuilds alerts.
    """
    _ensure_dirs()
    if disposition not in {"true_hit", "false_positive", "escalate"}:
        raise ValueError("disposition must be true_hit | false_positive | escalate")

    event = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "alert_id": alert_id,
        "disposition": disposition,
        "rationale": rationale,
        "actor_user_id": actor_user_id,
        "alert_type": (alert or {}).get("alert_type"),
        "feedback_key": (alert or {}).get("feedback_key") or (alert or {}).get("alert_type"),
        "list_id": (alert or {}).get("list_id"),
        "counterparty_name": (alert or {}).get("counterparty_name"),
    }
    with open(_dispositions_path(), "a", encoding="utf-8") as f:
        f.write(json.dumps(event, default=str) + "\n")

    # Update understanding alerts file disposition fields
    alerts_path = UNDERSTANDING_DIR / "alerts.json"
    if alerts_path.exists():
        with open(alerts_path, encoding="utf-8") as f:
            alerts = json.load(f)
        for a in alerts:
            if a.get("alert_id") == alert_id:
                a["disposition"] = disposition
                a["rationale"] = rationale
                a["status"] = "closed" if disposition != "escalate" else "escalated"
        with open(alerts_path, "w", encoding="utf-8") as f:
            json.dump(alerts, f, indent=2, default=str)

    _update_score_adjustments(event)
    _append_few_shot(event)

    # Rebuild alerts so future screening reflects new multipliers
    build_understanding(apply_feedback=True)
    return event


def _update_score_adjustments(event: dict[str, Any]) -> None:
    settings = load_settings()["feedback"]
    adj = load_feedback_adjustments()
    key = event.get("feedback_key") or event.get("alert_type") or "unknown"
    current = adj.get(key, 1.0)
    if event["disposition"] == "false_positive":
        current = max(settings["min_score_floor"], current * (1.0 - settings["false_positive_score_penalty"]))
    elif event["disposition"] == "true_hit":
        current = min(2.0, current * (1.0 + settings["true_hit_score_boost"]))
    # escalate: mild boost to keep visibility
    elif event["disposition"] == "escalate":
        current = min(2.0, current * 1.1)
    adj[key] = round(current, 4)
    with open(_adjustments_path(), "w", encoding="utf-8") as f:
        json.dump(adj, f, indent=2)


def _append_few_shot(event: dict[str, Any]) -> None:
    path = _few_shot_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    memory = {
        "alert_type": event.get("alert_type"),
        "counterparty_name": event.get("counterparty_name"),
        "disposition": event["disposition"],
        "rationale": event["rationale"],
    }
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(memory) + "\n")


def load_few_shots(limit: int = 8) -> list[dict[str, Any]]:
    path = _few_shot_path()
    if not path.exists():
        return []
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows[-limit:]


def reset_feedback() -> None:
    _ensure_dirs()
    for p in [
        _dispositions_path(),
        _adjustments_path(),
        _few_shot_path(),
    ]:
        if p.exists():
            p.unlink()
    build_understanding(apply_feedback=False)


def before_after_snapshot(feedback_key: str) -> dict[str, Any]:
    """Utility for demos: compare multipliers and matching alert scores."""
    adj = load_feedback_adjustments()
    with open(UNDERSTANDING_DIR / "alerts.json", encoding="utf-8") as f:
        alerts = json.load(f)
    related = [a for a in alerts if (a.get("feedback_key") or a.get("alert_type")) == feedback_key]
    return {
        "feedback_key": feedback_key,
        "multiplier": adj.get(feedback_key, 1.0),
        "alerts": [
            {
                "alert_id": a["alert_id"],
                "score": a["score"],
                "counterparty_name": a.get("counterparty_name"),
                "summary": a.get("summary"),
                "disposition": a.get("disposition"),
            }
            for a in related
        ],
    }