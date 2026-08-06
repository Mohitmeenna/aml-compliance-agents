#!/usr/bin/env python
"""Interactive / one-shot ask helper."""

import argparse
import json

from src.agents import Orchestrator


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--user", required=True)
    p.add_argument("--question", "-q", required=True)
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    result = Orchestrator(args.user).ask(args.question)
    if args.json:
        print(
            json.dumps(
                {
                    "answer": result.answer,
                    "denied": result.denied,
                    "role": result.role,
                    "handoff": result.handoff,
                    "agent_trace": result.agent_trace,
                },
                indent=2,
                default=str,
            )
        )
    else:
        print(result.answer)


if __name__ == "__main__":
    main()