#!/usr/bin/env python
"""Regenerate understanding artifacts from raw data."""

from src.understanding import build_understanding


def main() -> None:
    artifacts = build_understanding(apply_feedback=True)
    meta = {
        "obligations": len(artifacts["obligations"]),
        "profiles": len(artifacts["profiles"]),
        "alerts": len(artifacts["alerts"]),
        "chunks": len(artifacts["regulatory_chunks"]),
        "feedback_keys": list(artifacts["feedback_adjustments_applied"].keys()),
    }
    print("Understanding built:", meta)


if __name__ == "__main__":
    main()