#!/usr/bin/env python
"""One-shot bootstrap: generate data + build understanding."""

from scripts.generate_data import main as gen
from src.understanding import build_understanding


def main() -> None:
    gen()
    build_understanding(apply_feedback=False)
    print("Bootstrap complete.")


if __name__ == "__main__":
    main()