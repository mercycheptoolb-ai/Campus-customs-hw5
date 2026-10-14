"""Boss — reads each ticket, decides who should work on it, and makes the final call."""

from agents.base import make_agent
from models import AgentSpec, BossDecision

SPEC = AgentSpec(
    name="Boss",
    emoji="👑",
    role="Reads each ticket, decides who should work on it, and makes final calls.",
    prompt_file="boss.md",
    tools=("get_today", "get_ticket", "list_tickets", "get_cash", "list_approvals", "list_payments", "add_ticket_note", "update_ticket_status"),
    output_type=BossDecision,
)

agent = make_agent(SPEC)
