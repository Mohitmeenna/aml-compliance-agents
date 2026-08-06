"""CLI query interface."""

from __future__ import annotations

import json
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel

from src.agents import Orchestrator
from src.config import list_users
from src.feedback import before_after_snapshot, record_disposition, reset_feedback
from src.understanding import load_understanding

console = Console()


@click.group()
def cli() -> None:
    """AML compliance multi-agent desk."""


@cli.command("users")
def users_cmd() -> None:
    for u in list_users():
        console.print(f"{u['id']:12}  role={u['role']:22}  name={u['name']}  portfolios={u.get('portfolio_ids')}")


@cli.command("ask")
@click.option("--user", "user_id", required=True, help="User id from config/roles.yaml")
@click.option("--question", "-q", required=True)
@click.option("--json-out", is_flag=True, default=False)
def ask_cmd(user_id: str, question: str, json_out: bool) -> None:
    orch = Orchestrator(user_id)
    result = orch.ask(question)
    if json_out:
        click.echo(
            json.dumps(
                {
                    "user_id": result.user_id,
                    "role": result.role,
                    "denied": result.denied,
                    "answer": result.answer,
                    "handoff": result.handoff,
                    "agent_trace": result.agent_trace,
                },
                indent=2,
                default=str,
            )
        )
        return
    console.print(Panel(result.answer, title=f"{result.role} / {result.user_id}"))
    console.print(f"denied={result.denied}  trace={result.agent_trace}")
    if result.handoff:
        console.print(f"handoff={result.handoff}")


@cli.command("dispose")
@click.option("--user", "user_id", required=True)
@click.option("--alert-id", required=True)
@click.option("--disposition", type=click.Choice(["true_hit", "false_positive", "escalate"]), required=True)
@click.option("--rationale", required=True)
def dispose_cmd(user_id: str, alert_id: str, disposition: str, rationale: str) -> None:
    from src.rbac import DataGate, AccessDenied

    gate = DataGate(user_id)
    if not gate.can_disposition():
        raise click.ClickException("Access denied: role cannot disposition alerts.")
    understanding = load_understanding()
    alert = next((a for a in understanding["alerts"] if a["alert_id"] == alert_id), None)
    if not alert:
        raise click.ClickException(f"Unknown alert_id {alert_id}")
    # portfolio scope
    visible = gate.filter_alerts([alert])
    if not visible:
        raise click.ClickException("Access denied: alert outside portfolio scope.")
    event = record_disposition(
        alert_id=alert_id,
        disposition=disposition,
        rationale=rationale,
        actor_user_id=user_id,
        alert=alert,
    )
    console.print(Panel(json.dumps(event, indent=2), title="Disposition recorded — understanding rebuilt"))
    key = alert.get("feedback_key") or alert.get("alert_type")
    console.print(before_after_snapshot(key))


@cli.command("feedback-demo")
def feedback_demo_cmd() -> None:
    """Show before/after score change when a fuzzy sanctions alert is marked false_positive."""
    reset_feedback()
    understanding = load_understanding()
    # Find fuzzy Kim Song alert
    target = None
    for a in understanding["alerts"]:
        if a.get("alert_type") == "sanctions_match" and "Kim Song" in str(a.get("counterparty_name", "")):
            target = a
            break
    if not target:
        # fallback first sanctions_match that isn't TEHRAN
        for a in understanding["alerts"]:
            if a.get("alert_type") == "sanctions_match" and "TEHRAN" not in str(a.get("counterparty_name", "")).upper():
                target = a
                break
    if not target:
        raise click.ClickException("No suitable fuzzy sanctions alert found.")

    key = target.get("feedback_key") or target.get("alert_type")
    before = before_after_snapshot(key)
    console.print(Panel(json.dumps(before, indent=2), title="BEFORE feedback"))

    record_disposition(
        alert_id=target["alert_id"],
        disposition="false_positive",
        rationale="Commercial Singapore entity; not the DPRK SDN individual Kim Song Chol.",
        actor_user_id="u_analyst",
        alert=target,
    )
    after = before_after_snapshot(key)
    console.print(Panel(json.dumps(after, indent=2), title="AFTER false_positive disposition"))
    console.print(
        f"Multiplier {before['multiplier']} -> {after['multiplier']}. "
        "Future screening scores for this feedback_key are reduced."
    )


if __name__ == "__main__":
    cli()