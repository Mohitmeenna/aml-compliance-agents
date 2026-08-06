"""Build understanding artifacts: obligations, profiles, alerts, BM25 index metadata."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from rank_bm25 import BM25Okapi

from src.config import load_settings
from src.ingestion import ingest_all
from src.paths import UNDERSTANDING_DIR, FEEDBACK_DIR
from src.rbac.sanitize import looks_like_injection, sanitize_untrusted_text


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def extract_obligations(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Lightweight obligation/threshold extraction from regulatory chunks."""
    obligations = []
    patterns = [
        (r"usd\s*10,?000|\$\s*10,?000|ctr threshold", "cash_ctr_threshold", 10000),
        (r"three or more|3 or more", "structuring_count", 3),
        (r"seven days|7 days", "structuring_window_days", 7),
        (r"shell.?bank", "shell_bank_prohibition", None),
        (r"nested correspondent|payable-through", "correspondent_edd", None),
        (r"suspicious activity report|sar", "sar_filing", None),
        (r"politically exposed|pep", "pep_edd", None),
        (r"sanctions screening", "sanctions_screening", None),
    ]
    for ch in chunks:
        text = ch["text"]
        low = text.lower()
        for pat, obl_type, value in patterns:
            if re.search(pat, low):
                obligations.append(
                    {
                        "obligation_id": f"OBL-{len(obligations)+1:04d}",
                        "type": obl_type,
                        "value": value,
                        "chunk_id": ch["chunk_id"],
                        "doc_id": ch["doc_id"],
                        "excerpt": text[:280],
                    }
                )
    return obligations


def build_counterparty_profiles(
    customers: list[dict[str, Any]], transactions: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    by_cust = defaultdict(list)
    for t in transactions:
        by_cust[t["customer_id"]].append(t)
    cust_map = {c["customer_id"]: c for c in customers}
    profiles = []
    for cid, txns in by_cust.items():
        c = cust_map.get(cid, {})
        total = sum(float(t["amount_usd"]) for t in txns)
        profiles.append(
            {
                "customer_id": cid,
                "portfolio_id": c.get("portfolio_id"),
                "risk_rating": c.get("risk_rating"),
                "country": c.get("country"),
                "is_pep": c.get("is_pep"),
                "txn_count": len(txns),
                "total_volume_usd": round(total, 2),
                "high_risk_corridors": sorted(
                    {
                        t["counterparty_country"]
                        for t in txns
                        if t.get("counterparty_country") in {"IR", "KP", "SY", "MM", "YE", "PA", "BZ"}
                    }
                ),
                "injection_flags": [
                    t["transaction_id"]
                    for t in txns
                    if looks_like_injection(t.get("remittance_info"))
                ],
            }
        )
    return profiles


def _name_tokens(name: str) -> set[str]:
    stop = {"llc", "ltd", "pte", "sa", "inc", "the", "bank", "trading", "via", "nested"}
    return {t for t in _tokenize(name) if t not in stop and len(t) > 2}


def sanctions_score(counterparty: str, entry: dict[str, Any]) -> float:
    cp = _name_tokens(counterparty)
    if not cp:
        return 0.0
    names = _name_tokens(entry.get("name", "")) | _name_tokens(entry.get("aliases", ""))
    if not names:
        return 0.0
    overlap = cp & names
    if not overlap:
        return 0.0
    # Exact-ish: all significant tokens of list name appear
    if names <= cp or cp <= names:
        return 0.95
    jaccard = len(overlap) / len(names | cp)
    return round(min(0.9, 0.4 + jaccard), 3)


def generate_alerts(
    transactions: list[dict[str, Any]],
    customers: list[dict[str, Any]],
    sanctions: list[dict[str, Any]],
    feedback_adjustments: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    settings = load_settings()
    scr = settings["screening"]
    feedback_adjustments = feedback_adjustments or {}
    cust_map = {c["customer_id"]: c for c in customers}
    alerts: list[dict[str, Any]] = []
    aid = 1

    def emit(**kwargs):
        nonlocal aid
        alert_type = kwargs["alert_type"]
        base = float(kwargs.get("score", 0.7))
        # Feedback-driven score adjustment by alert_type or counterparty key
        adj_key = kwargs.get("feedback_key") or alert_type
        mult = feedback_adjustments.get(adj_key, 1.0)
        score = max(settings["feedback"]["min_score_floor"], min(1.0, base * mult))
        kwargs["score"] = round(score, 3)
        kwargs["alert_id"] = f"AL-{aid:04d}"
        kwargs.setdefault("status", "open")
        kwargs.setdefault("disposition", None)
        kwargs.setdefault("rationale", None)
        aid += 1
        alerts.append(kwargs)

    # Structuring detection
    cash_by_cust: dict[str, list] = defaultdict(list)
    for t in transactions:
        if t.get("is_cash") and float(t["amount_usd"]) < scr["cash_threshold_usd"]:
            cash_by_cust[t["customer_id"]].append(t)

    window = scr["structuring_window_days"]
    for cid, txns in cash_by_cust.items():
        txns = sorted(txns, key=lambda x: x["txn_date"])
        for i in range(len(txns)):
            start = datetime.strptime(txns[i]["txn_date"], "%Y-%m-%d")
            group = [
                t
                for t in txns
                if start
                <= datetime.strptime(t["txn_date"], "%Y-%m-%d")
                <= start + timedelta(days=window)
            ]
            if len(group) >= scr["structuring_count"]:
                c = cust_map.get(cid, {})
                emit(
                    alert_type="structuring",
                    customer_id=cid,
                    portfolio_id=c.get("portfolio_id"),
                    transaction_ids=[t["transaction_id"] for t in group],
                    counterparty_name="CASH",
                    account_number=group[0].get("account_number"),
                    score=0.82,
                    created_at=group[-1]["txn_date"],
                    rule_refs=["cash_ctr_threshold", "structuring_count"],
                    summary=f"{len(group)} sub-threshold cash txns within {window} days",
                    feedback_key="structuring",
                )
                break

    # Sanctions + correspondent + high-risk country
    for t in transactions:
        c = cust_map.get(t["customer_id"], {})
        # sanitize remittance for downstream agents
        rem = sanitize_untrusted_text(t.get("remittance_info"))
        inj = looks_like_injection(t.get("remittance_info"))

        best = (0.0, None)
        for s in sanctions:
            sc = sanctions_score(str(t.get("counterparty_name", "")), s)
            if sc > best[0]:
                best = (sc, s)
        if best[0] >= 0.55:
            emit(
                alert_type="sanctions_match",
                customer_id=t["customer_id"],
                portfolio_id=c.get("portfolio_id"),
                transaction_ids=[t["transaction_id"]],
                counterparty_name=t.get("counterparty_name"),
                account_number=t.get("account_number"),
                score=best[0],
                created_at=t["txn_date"],
                rule_refs=["sanctions_screening"],
                summary=f"Possible match to {best[1]['list_id']} ({best[1]['name']})",
                list_id=best[1]["list_id"],
                sanitized_remittance=rem,
                injection_flag=inj,
                feedback_key=f"sanctions::{best[1]['list_id']}",
            )

        raw_flag = t.get("correspondent_flag")
        flag = "" if raw_flag is None or (isinstance(raw_flag, float) and str(raw_flag) == "nan") else str(raw_flag).strip()
        if flag in scr["correspondent_high_risk_flags"]:
            emit(
                alert_type="correspondent_banking",
                customer_id=t["customer_id"],
                portfolio_id=c.get("portfolio_id"),
                transaction_ids=[t["transaction_id"]],
                counterparty_name=t.get("counterparty_name"),
                account_number=t.get("account_number"),
                score=0.88,
                created_at=t["txn_date"],
                rule_refs=["correspondent_edd"],
                summary=f"Correspondent risk flag: {flag}",
                correspondent_flag=flag,
                sanitized_remittance=rem,
                injection_flag=inj,
                feedback_key="correspondent_banking",
            )

        if t.get("counterparty_country") in scr["high_risk_countries"] and best[0] < 0.55:
            emit(
                alert_type="high_risk_jurisdiction",
                customer_id=t["customer_id"],
                portfolio_id=c.get("portfolio_id"),
                transaction_ids=[t["transaction_id"]],
                counterparty_name=t.get("counterparty_name"),
                account_number=t.get("account_number"),
                score=0.65,
                created_at=t["txn_date"],
                rule_refs=["high_risk_corridor"],
                summary=f"Payment corridor to {t.get('counterparty_country')}",
                sanitized_remittance=rem,
                injection_flag=inj,
                feedback_key="high_risk_jurisdiction",
            )

    return alerts


def build_bm25_index(chunks: list[dict[str, Any]]) -> dict[str, Any]:
    corpus = [_tokenize(c["text"]) for c in chunks]
    # Persist serializable form; rebuild BM25 at runtime from tokens
    return {
        "chunk_ids": [c["chunk_id"] for c in chunks],
        "tokens": corpus,
    }


class RegulatoryIndex:
    def __init__(self, chunks: list[dict[str, Any]], index_blob: dict[str, Any] | None = None):
        self.chunks = {c["chunk_id"]: c for c in chunks}
        self.order = [c["chunk_id"] for c in chunks]
        tokens = (index_blob or {}).get("tokens") or [_tokenize(c["text"]) for c in chunks]
        self.bm25 = BM25Okapi(tokens)

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        scores = self.bm25.get_scores(_tokenize(query))
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_k]
        out = []
        for idx, score in ranked:
            if score <= 0:
                continue
            cid = self.order[idx]
            ch = dict(self.chunks[cid])
            ch["score"] = float(score)
            out.append(ch)
        return out


def load_feedback_adjustments() -> dict[str, float]:
    path = FEEDBACK_DIR / "score_adjustments.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_understanding(*, apply_feedback: bool = True) -> dict[str, Any]:
    UNDERSTANDING_DIR.mkdir(parents=True, exist_ok=True)
    FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)

    raw = ingest_all()
    obligations = extract_obligations(raw["regulatory_chunks"])
    profiles = build_counterparty_profiles(raw["customers"], raw["transactions"])
    adjustments = load_feedback_adjustments() if apply_feedback else {}
    alerts = generate_alerts(
        raw["transactions"], raw["customers"], raw["sanctions"], adjustments
    )
    index_blob = build_bm25_index(raw["regulatory_chunks"])

    schema_notes = {
        "precomputed": [
            "regulatory chunking + BM25 token index",
            "obligation/threshold extraction",
            "counterparty activity profiles",
            "baseline screening alerts with feedback-adjusted scores",
        ],
        "on_the_fly": [
            "RBAC filtering/masking per request",
            "query planning and natural-language synthesis (LLM)",
            "alert investigation assembly from live filtered tables",
        ],
        "why": (
            "Parsing PDFs and re-scoring the full ledger on every question is wasteful; "
            "access decisions and answer synthesis must stay request-scoped so RBAC cannot be bypassed by cached answers."
        ),
    }

    artifacts = {
        "built_at": datetime.utcnow().isoformat() + "Z",
        "obligations": obligations,
        "profiles": profiles,
        "alerts": alerts,
        "regulatory_chunks": raw["regulatory_chunks"],
        "bm25_index": index_blob,
        "schema_notes": schema_notes,
        "feedback_adjustments_applied": adjustments,
    }

    def dump(name: str, obj: Any) -> None:
        with open(UNDERSTANDING_DIR / name, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2, default=str)

    dump("obligations.json", obligations)
    dump("profiles.json", profiles)
    dump("alerts.json", alerts)
    dump("regulatory_chunks.json", raw["regulatory_chunks"])
    dump("bm25_index.json", index_blob)
    dump("schema_notes.json", schema_notes)
    dump("understanding_meta.json", {
        "built_at": artifacts["built_at"],
        "counts": {
            "obligations": len(obligations),
            "profiles": len(profiles),
            "alerts": len(alerts),
            "chunks": len(raw["regulatory_chunks"]),
        },
        "feedback_keys": list(adjustments.keys()),
    })
    return artifacts


def load_understanding() -> dict[str, Any]:
    required = [
        "obligations.json",
        "profiles.json",
        "alerts.json",
        "regulatory_chunks.json",
        "bm25_index.json",
    ]
    missing = [n for n in required if not (UNDERSTANDING_DIR / n).exists()]
    if missing:
        return build_understanding()
    out = {}
    for n in required:
        with open(UNDERSTANDING_DIR / n, encoding="utf-8") as f:
            out[n.replace(".json", "")] = json.load(f)
    # normalize keys
    return {
        "obligations": out["obligations"],
        "profiles": out["profiles"],
        "alerts": out["alerts"],
        "regulatory_chunks": out["regulatory_chunks"],
        "bm25_index": out["bm25_index"],
    }