"""Facilities — handles the shop space side: leases, rent, landlord notices."""

from agents.base import make_agent
from models import AgentSpec

SPEC = AgentSpec(
    name="Facilities",
    emoji="🏠",
    role="Handles the shop space side: leases, rent, and landlord notices.",
    prompt_file="facilities.md",
    tools=("get_today", "get_rent_due", "get_cash", "list_approvals", "add_ticket_note"),
)

agent = make_agent(SPEC)
