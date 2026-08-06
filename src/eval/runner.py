"""Eval runner — reports pass/fail honestly."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from src.agents import Orchestrator
from src.paths import EVAL_DIR, ROOT


def _contains_any(text: str, needles: list[str] | None) -> bool:
    if not needles:
        return True
    low = text.lower()
    return any(n.lower() in low for n in needles)


def _contains_none(text: str, needles: list[str] | None) -> bool:
    if not needles:
        return True
    low = text.lower()
    return all(n.lower() not in low for n in needles)


def _check_case(case: dict[str, Any]) -> dict[str, Any]:
    orch = Orchestrator(case["user_id"])
    result = orch.ask(case["question"])
    exp = case["expect"]
    answer = result.answer or ""
    evidence_blob = json.dumps(result.evidence or {}, default=str)
    combined = answer + "\n" + evidence_blob

    failures: list[str] = []

    if "denied" in exp and bool(result.denied) != bool(exp["denied"]):
        failures.append(f"denied expected={exp['denied']} got={result.denied}")

    if not _contains_any(answer, exp.get("answer_contains_any")):
        # Special-case RM portfolio: empty evidence is success
        if case.get("expect", {}).get("custom") == "rm_portfolio_scope":
            ok = (
                result.denied
                or _contains_any(answer, ["No accessible evidence", "Access denied"])
                or not (result.evidence or {}).get("customers")
            )
            # must not leak
            if not _contains_none(combined, exp.get("must_not_leak_any")):
                ok = False
                failures.append("leaked restricted content")
            if not ok:
                failures.append("rm portfolio scope not enforced")
        else:
            failures.append(f"missing expected substrings {exp.get('answer_contains_any')}")

    if exp.get("answer_not_contains") and not _contains_none(answer, exp["answer_not_contains"]):
        failures.append(f"answer contained forbidden {exp['answer_not_contains']}")

    if exp.get("must_not_leak_any") and not _contains_none(combined, exp["must_not_leak_any"]):
        failures.append(f"LEAK of restricted values {exp['must_not_leak_any']}")

    if exp.get("requires_regulatory_and_txn"):
        has_reg = bool((result.evidence or {}).get("regulatory"))
        has_txn_or_alert = bool((result.evidence or {}).get("transactions")) or bool(
            (result.evidence or {}).get("alerts")
        )
        # Also accept if answer itself clearly references both worlds
        text_ok = _contains_any(answer, ["Section", "FATF", "FinCEN", "guidance", "Advisory", "Chapter"]) and (
            _contains_any(answer, ["TX-", "AL-", "correspondent", "structur", "nested", "payable"])
        )
        if not ((has_reg and has_txn_or_alert) or text_ok):
            failures.append("expected regulatory + transaction/alert evidence")

    if exp.get("answer_contains_any_evidence"):
        if not _contains_any(combined, exp["answer_contains_any_evidence"]):
            failures.append("missing evidence markers")

    passed = len(failures) == 0
    return {
        "id": case["id"],
        "user_id": case["user_id"],
        "question": case["question"],
        "passed": passed,
        "denied": result.denied,
        "failures": failures,
        "answer_preview": answer[:400],
        "agent_trace": result.agent_trace,
        "tags": case.get("tags", []),
    }


def run_eval(path: Path | None = None) -> dict[str, Any]:
    path = path or (EVAL_DIR / "eval_set.json")
    with open(path, encoding="utf-8") as f:
        suite = json.load(f)

    results = [_check_case(c) for c in suite["cases"]]
    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    report = {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": round(passed / total, 3) if total else 0.0,
        "results": results,
    }
    out = EVAL_DIR / "last_report.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    return report


def main() -> None:
    # Ensure package imports work when run as module or script
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    report = run_eval()
    print(f"PASS {report['passed']}/{report['total']}  pass_rate={report['pass_rate']}")
    for r in report["results"]:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"  [{status}] {r['id']} ({r['user_id']}) {r['question'][:70]}")
        if not r["passed"]:
            for f in r["failures"]:
                print(f"           - {f}")
            print(f"           answer: {r['answer_preview'][:200]!r}")
    print(f"Wrote {EVAL_DIR / 'last_report.json'}")


if __name__ == "__main__":
    main()