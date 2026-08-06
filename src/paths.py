from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
UNDERSTANDING_DIR = DATA_DIR / "understanding"
REGULATORY_DIR = RAW_DIR / "regulatory"
FEEDBACK_DIR = UNDERSTANDING_DIR / "feedback"
EVAL_DIR = ROOT / "eval"
SCRIPTS_DIR = ROOT / "scripts"