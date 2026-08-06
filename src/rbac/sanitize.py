"""Sanitize untrusted text (remittance / counterparty / user input) against prompt injection."""

from __future__ import annotations

import re

_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions",
    r"disregard\s+(all\s+)?(previous|prior|above)",
    r"you\s+are\s+now\s+",
    r"system\s*:\s*",
    r"<\|?(system|assistant|user)\|?>",
    r"reveal\s+(your\s+)?(system\s+)?prompt",
    r"jailbreak",
    r"do\s+not\s+follow\s+(your\s+)?(safety|compliance)\s+rules",
]


def sanitize_untrusted_text(text: str | None, *, max_len: int = 500) -> str:
    if not text:
        return ""
    cleaned = str(text)[:max_len]
    for pat in _INJECTION_PATTERNS:
        cleaned = re.sub(pat, "[FILTERED]", cleaned, flags=re.IGNORECASE)
    # Neutral wrapper so models treat remittance as data, not instructions
    return f"<<UNTRUSTED_PAYMENT_NARRATIVE>>{cleaned}<<END_UNTRUSTED>>"


def looks_like_injection(text: str | None) -> bool:
    if not text:
        return False
    for pat in _INJECTION_PATTERNS:
        if re.search(pat, str(text), flags=re.IGNORECASE):
            return True
    return False