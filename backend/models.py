"""Data types shared by the Campus Customs agent team.

- Names and statuses (Literal types) so a typo can't route work to a missing agent.
- Ticket: one row of the tickets table, as the Boss receives it.
- AgentSpec: what defines one agent (role, prompt file, MCP tools, output type).
- AgentReport / BossDecision: the structured output each agent's loop must end with.
- TicketState / TeamDeps: per-ticket run state passed to every agent as PydanticAI deps.
- DelegationResult / TicketOutcome: what `delegate` and a ticket run return.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal

from pydantic import BaseModel, Field

AgentName = Literal["Boss", "Inventory", "Accounting", "Facilities", "Customer Service"]
TicketStatus = Literal["open", "in_progress", "awaiting_approval", "blocked", "resolved"]
TicketType = Literal["customer_order", "rent_notice", "price_override"]

Emit = Callable[..., None]


class Ticket(BaseModel):
    """One row of the tickets table."""

    id: int
    type: str
    requester: str
    subject: str
    sku: str | None = None
    size: str | None = None
    qty: int | None = None
    lease_id: int | None = None
    invoice_id: int | None = None
    status: str
    notes: str | None = None
    created_at: str


class AgentReport(BaseModel):
    """What a specialist (Inventory, Accounting, Facilities, Customer Service) hands back to whoever asked."""

    ticket_id: int
    findings: list[str] = Field(description="Facts checked with tools: stock, prices, dates, balances, vendors. Include the numbers.")
    actions_taken: list[str] = Field(
        default_factory=list,
        description="Things you created, with their ids (approval #, purchase order #, draft #, note). Empty if none.",
    )
    blockers: list[str] = Field(default_factory=list, description="What stops this work right now (cash, open invoice, waiting on a human).")
    summary: str = Field(description="One or two sentences for the agent who asked.")

    def as_text(self) -> str:
        parts = [self.summary]
        if self.findings:
            parts.append("Findings: " + "; ".join(self.findings))
        if self.actions_taken:
            parts.append("Actions: " + "; ".join(self.actions_taken))
        if self.blockers:
            parts.append("Blockers: " + "; ".join(self.blockers))
        return "\n".join(parts)


class BossDecision(BaseModel):
    """The Boss's final call on a ticket. Must match the status it set with update_ticket_status."""

    ticket_id: int
    final_status: TicketStatus
    delegated_to: list[AgentName] = Field(default_factory=list, description="Teammates who worked on this ticket.")
    decision: str = Field(description="2–4 sentences: what was decided and why.")
    human_actions: list[str] = Field(
        default_factory=list,
        description="What the human must do on the dashboard (e.g. 'Approve request #1: pay invoice 501, $840'). Empty if nothing.",
    )

    def as_text(self) -> str:
        text = f"[{self.final_status}] {self.decision}"
        if self.human_actions:
            text += "\nFor the human: " + "; ".join(self.human_actions)
        return text


AgentOutput = AgentReport | BossDecision


@dataclass(frozen=True)
class AgentSpec:
    """Everything that defines one agent on the team."""

    name: AgentName
    emoji: str
    role: str
    prompt_file: str  # file name under backend/prompts/
    tools: tuple[str, ...]  # MCP tools this agent may call (delegate is added for everyone)
    output_type: type[AgentReport] | type[BossDecision] = AgentReport


@dataclass
class TicketState:
    """Shared across every agent working on one ticket — counts delegations so the team can't loop forever."""

    ticket_id: int
    emit: Emit
    run_id: str = ""  # ties every audit record of one board run together
    delegations: int = 0
    next_id: int = 0


@dataclass
class TeamDeps:
    """PydanticAI deps for one agent run: who is acting, who asked (the chain), and the ticket state."""

    agent: AgentName
    chain: tuple[AgentName, ...]
    ticket: TicketState
    extra: dict[str, Any] = field(default_factory=dict)


class DelegationResult(BaseModel):
    """What the `delegate` tool returns to the agent that asked for help."""

    agent: str
    status: Literal["done", "error"]
    report: AgentReport | BossDecision | None = None
    reply: str = ""


class TicketOutcome(BaseModel):
    ticket_id: int
    status: Literal["done", "error"]
    decision: BossDecision | None = None
    summary: str
    delegations: int = 0
