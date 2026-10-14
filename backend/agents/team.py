"""Running the ticket board with the five-agent team.

run_board() works the board one ticket at a time (cash is shared, so order matters).
For each ticket the Boss's agent loop reads it, delegates to teammates (who may delegate
to each other — see base.delegate), sets the final status, and returns a BossDecision.

Shop rule: a full run always resets the working database to the original values first.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

import audit
from agents import AGENTS, SPECS, shop_mcp
from agents.base import output_text, run_agent
from agents.config import MODEL_NAME
from agents.events import clip
from models import BossDecision, Emit, TeamDeps, Ticket, TicketOutcome, TicketState


async def run_ticket(ticket: Ticket, emit: Emit, run_id: str = "") -> TicketOutcome:
    state = TicketState(ticket_id=ticket.id, emit=emit, run_id=run_id)
    emit("ticket_started", ticket_id=ticket.id, subject=ticket.subject, ticket_type=ticket.type)
    prompt = (
        f"New work on ticket #{ticket.id}. Ticket record:\n```json\n{json.dumps(ticket.model_dump(), indent=1)}\n```\n"
        "Read it with get_ticket (for its log), work it with your team, set its final status, and return your decision."
    )
    decision: BossDecision | None = None
    try:
        output, usage = await run_agent("Boss", prompt, TeamDeps(agent="Boss", chain=("Boss",), ticket=state))
        decision = output if isinstance(output, BossDecision) else None
        summary, status = output_text(output), "done"
    except Exception as exc:
        summary, usage, status = f"Ticket run failed: {clip(exc, 400)}", None, "error"
    emit(
        "ticket_done",
        ticket_id=ticket.id,
        summary=clip(summary, 1500),
        status=status,
        final_status=decision.final_status if decision else None,
        delegations=state.delegations,
        usage=usage,
    )
    return TicketOutcome(ticket_id=ticket.id, status=status, decision=decision, summary=summary, delegations=state.delegations)


async def tickets_to_work(full_run: bool) -> list[Ticket]:
    """Full run: every open ticket. Continue: unresolved tickets with no request still waiting on the human."""
    tickets = [Ticket(**t) for t in await shop_mcp.call("list_tickets")]
    if full_run:
        return [t for t in tickets if t.status == "open"]
    approvals = await shop_mcp.call("list_approvals", status="pending")
    waiting = {a["ticket_id"] for a in approvals}
    return [t for t in tickets if t.status != "resolved" and t.id not in waiting]


run_lock = asyncio.Lock()


async def _run(emit: Emit, todo: list[Ticket], *, full_run: bool, run_id: str) -> list[TicketOutcome]:
    today = (await shop_mcp.call("get_today")).get("today")
    emit("run_started", full_run=full_run, ticket_ids=[t.id for t in todo])
    audit.append("run_started", run_id=run_id, full_run=full_run, shop_today=today, ticket_ids=[t.id for t in todo], model=MODEL_NAME)
    results = []
    for ticket in todo:
        results.append(await run_ticket(ticket, emit, run_id))
    emit("run_done", results=[r.model_dump() for r in results])
    audit.append("run_finished", run_id=run_id, results=[r.model_dump() for r in results])
    return results


async def run_board(emit: Emit, *, full_run: bool, ticket_ids: list[int] | None = None) -> list[TicketOutcome]:
    """Work the board. A full run always resets the working DB to the original first."""
    run_id = uuid.uuid4().hex[:12]
    if full_run:
        reset = await shop_mcp.call("admin_reset_database")
        emit("db_reset", note="Working copy restored from campus_customs.db before the full run.")
        audit.append("db_reset", run_id=run_id, result=reset)
    todo = await tickets_to_work(full_run)
    if ticket_ids:
        todo = [t for t in todo if t.id in ticket_ids]
    return await _run(emit, todo, full_run=full_run, run_id=run_id)


async def run_one_ticket(emit: Emit, ticket: Ticket) -> TicketOutcome:
    """Run the team on one ticket as it stands now (no reset). The Boss continues from the ticket's log."""
    results = await _run(emit, [ticket], full_run=False, run_id=uuid.uuid4().hex[:12])
    return results[0]


def roster() -> list[dict[str, Any]]:
    return [
        {"name": s.name, "emoji": s.emoji, "role": s.role, "tools": [*s.tools, "delegate"], "output": s.output_type.__name__}
        for s in SPECS.values()
        if s.name in AGENTS
    ]
