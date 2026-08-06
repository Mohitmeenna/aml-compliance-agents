"""Role-based access control enforced at the data layer (not UI / not prompt-only)."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from src.config import get_user, load_roles


class AccessDenied(Exception):
    """Raised when a role cannot access a resource. Message must not leak content."""

    def __init__(self, resource: str, reason: str = "insufficient permissions"):
        self.resource = resource
        self.reason = reason
        super().__init__(f"ACCESS_DENIED: {resource} — {reason}")


def _mask_value(field: str, value: Any, masking_rules: dict[str, str]) -> Any:
    if value is None or value == "":
        return value
    s = str(value)
    rule = masking_rules.get(field, "redact")
    if rule == "allow":
        return value
    if rule == "redact":
        return "[REDACTED]"
    if rule == "last4":
        return ("*" * max(0, len(s) - 4)) + s[-4:] if len(s) >= 4 else "****"
    if rule == "partial":
        parts = re.split(r"(\s+)", s)
        out = []
        for p in parts:
            if not p.strip():
                out.append(p)
            else:
                out.append(p[0] + ("*" * max(0, len(p) - 1)))
        return "".join(out)
    return "[REDACTED]"


class DataGate:
    """Single choke point for all data reads used by agents."""

    def __init__(self, user_id: str):
        self.user = get_user(user_id)
        self.user_id = user_id
        self.role = self.user["role"]
        self.permissions = self.user["permissions"]
        self.portfolio_ids = set(self.user.get("portfolio_ids") or [])
        roles_cfg = load_roles()
        self.pii_fields = roles_cfg["pii_fields"]
        self.masking_rules = roles_cfg["masking"]

    def has(self, perm: str) -> bool:
        return perm in self.permissions

    def require(self, perm: str, resource: str) -> None:
        if not self.has(perm):
            raise AccessDenied(resource, f"role '{self.role}' lacks '{perm}'")

    def _portfolio_ok(self, record: dict[str, Any]) -> bool:
        if not self.has("portfolios.own"):
            return True
        if self.has("portfolios.all"):
            return True
        pf = record.get("portfolio_id")
        return pf in self.portfolio_ids

    def filter_customers(self, customers: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not (self.has("customers.read") or self.has("customers.read_pii")):
            raise AccessDenied("customers", "no customer read permission")

        out = []
        for c in customers:
            if not self._portfolio_ok(c):
                continue
            row = deepcopy(c)
            if not self.has("customers.read_pii"):
                for field in self.pii_fields["customers"]:
                    if field in row:
                        row[field] = _mask_value(field, row[field], self.masking_rules)
            if not self.has("customers.read_id_docs"):
                row.pop("id_document_number", None)
                row.pop("id_document_type", None)
                if "id_document_number" in (c or {}):
                    row["id_document_number"] = "[REDACTED]"
            out.append(row)
        return out

    def filter_transactions(self, txns: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not self.has("transactions.read"):
            raise AccessDenied("transactions", "no transaction read permission")

        out = []
        for t in txns:
            if not self._portfolio_ok(t):
                continue
            row = deepcopy(t)
            if not self.has("transactions.read_pii"):
                for field in self.pii_fields["transactions"]:
                    if field in row:
                        row[field] = _mask_value(field, row[field], self.masking_rules)
            out.append(row)
        return out

    def filter_alerts(
        self,
        alerts: list[dict[str, Any]],
        *,
        include_underlying_pii: bool = False,
    ) -> list[dict[str, Any]]:
        # Auditor gets summary-only view
        if self.has("alerts.read_summary") and not self.has("alerts.read"):
            out = []
            for a in alerts:
                if not self._portfolio_ok(a):
                    continue
                out.append(
                    {
                        "alert_id": a.get("alert_id"),
                        "alert_type": a.get("alert_type"),
                        "status": a.get("status"),
                        "score": a.get("score"),
                        "disposition": a.get("disposition"),
                        "rationale": a.get("rationale"),
                        "created_at": a.get("created_at"),
                        "customer_id": "[REDACTED]",
                        "transaction_ids": ["[REDACTED]"],
                        "counterparty_name": "[REDACTED]",
                    }
                )
            return out

        if not self.has("alerts.read"):
            raise AccessDenied("alerts", "no alert read permission")

        out = []
        for a in alerts:
            if not self._portfolio_ok(a):
                continue
            row = deepcopy(a)
            if not self.has("transactions.read_pii") and not include_underlying_pii:
                if "counterparty_name" in row:
                    row["counterparty_name"] = _mask_value(
                        "full_name", row["counterparty_name"], self.masking_rules
                    )
                if "account_number" in row:
                    row["account_number"] = _mask_value(
                        "account_number", row["account_number"], self.masking_rules
                    )
            out.append(row)
        return out

    def filter_sanctions(self, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not self.has("sanctions.read"):
            raise AccessDenied("sanctions", "no sanctions read permission")
        return deepcopy(entries)

    def filter_regulatory(self, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not self.has("regulatory.read"):
            raise AccessDenied("regulatory", "no regulatory read permission")
        return deepcopy(chunks)

    def filter_sar(self, sars: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not self.has("sar.read"):
            raise AccessDenied("sar", "role cannot access suspicious-activity reports")
        return deepcopy(sars)

    def filter_audit(self, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not self.has("audit.read"):
            raise AccessDenied("audit", "no audit read permission")
        # Strip payload PII for non-CCO
        out = []
        for e in events:
            row = deepcopy(e)
            if not self.has("customers.read_pii"):
                row["details"] = {
                    k: ("[REDACTED]" if k in {"customer_name", "account_number", "national_id"} else v)
                    for k, v in (row.get("details") or {}).items()
                }
            out.append(row)
        return out

    def can_disposition(self) -> bool:
        return self.has("alerts.disposition")


def refusal_message(exc: AccessDenied) -> str:
    """Standard refusal that never includes protected content."""
    return (
        f"Access denied. Your role does not permit access to '{exc.resource}'. "
        "No restricted data is included in this response."
    )