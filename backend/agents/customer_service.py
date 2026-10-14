"""Customer Service — drafts messages for customers. Drafts stay on the board and are never sent."""

from agents.base import make_agent
from models import AgentSpec

SPEC = AgentSpec(
    name="Customer Service",
    emoji="💌",
    role="Drafts messages for customers. Drafts stay on the board and are never sent.",
    prompt_file="customer_service.md",
    tools=("get_today", "get_ticket", "check_stock", "get_pricing", "list_drafts", "draft_customer_message", "add_ticket_note"),
)

agent = make_agent(SPEC)
