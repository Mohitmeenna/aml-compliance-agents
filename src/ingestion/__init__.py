"""Load raw CSV/XLSX/PDF/JSON into normalized in-memory / on-disk structures."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pandas as pd
from pypdf import PdfReader

from src.paths import RAW_DIR, REGULATORY_DIR


def _read_table(csv_name: str, xlsx_name: str) -> pd.DataFrame:
    csv_path = RAW_DIR / csv_name
    xlsx_path = RAW_DIR / xlsx_name
    if csv_path.exists():
        return pd.read_csv(csv_path)
    if xlsx_path.exists():
        return pd.read_excel(xlsx_path)
    raise FileNotFoundError(f"Missing {csv_name} / {xlsx_name} — run scripts/generate_data.py")


def load_customers() -> list[dict[str, Any]]:
    return _read_table("customers.csv", "customers.xlsx").to_dict(orient="records")


def load_transactions() -> list[dict[str, Any]]:
    df = _read_table("transactions.csv", "transactions.xlsx")
    if "is_cash" in df.columns:
        df["is_cash"] = df["is_cash"].fillna(False).astype(bool)
    # Empty CSV cells → NaN; normalize object columns to empty strings
    for col in df.select_dtypes(include=["object"]).columns:
        df[col] = df[col].fillna("")
    return df.to_dict(orient="records")


def load_sanctions() -> list[dict[str, Any]]:
    return _read_table("sanctions.csv", "sanctions.xlsx").to_dict(orient="records")


def load_sars() -> list[dict[str, Any]]:
    path = RAW_DIR / "sars.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_audit_trail() -> list[dict[str, Any]]:
    path = RAW_DIR / "audit_trail.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def extract_pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    parts = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    return "\n".join(parts)


def load_regulatory_documents() -> list[dict[str, Any]]:
    docs = []
    for path in sorted(REGULATORY_DIR.glob("*.pdf")):
        text = extract_pdf_text(path)
        docs.append(
            {
                "doc_id": path.stem,
                "path": str(path),
                "title": path.stem.replace("_", " "),
                "text": text,
            }
        )
    return docs


def chunk_document(doc: dict[str, Any], max_chars: int = 700) -> list[dict[str, Any]]:
    """Hierarchical-ish chunking: split on Section/Chapter/Advisory headings when present."""
    text = doc["text"]
    parts = re.split(r"(?=(?:Section|Chapter|Advisory|Indicator)\s+[0-9A-Z])", text)
    parts = [p.strip() for p in parts if p and p.strip()]
    if len(parts) <= 1:
        parts = []
        raw = text
        while raw:
            parts.append(raw[:max_chars])
            raw = raw[max_chars:]

    chunks = []
    for i, part in enumerate(parts):
        heading = part.split("\n", 1)[0][:120]
        chunks.append(
            {
                "chunk_id": f"{doc['doc_id']}::c{i}",
                "doc_id": doc["doc_id"],
                "title": doc["title"],
                "heading": heading,
                "text": part[: max_chars * 2],
                "source_path": doc["path"],
            }
        )
    return chunks


def ingest_all() -> dict[str, Any]:
    docs = load_regulatory_documents()
    chunks = []
    for d in docs:
        chunks.extend(chunk_document(d))
    return {
        "customers": load_customers(),
        "transactions": load_transactions(),
        "sanctions": load_sanctions(),
        "sars": load_sars(),
        "audit_trail": load_audit_trail(),
        "regulatory_docs": docs,
        "regulatory_chunks": chunks,
    }