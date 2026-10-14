"""Inventory — checks stock by SKU and size, spots shortfalls, and figures out which vendor can restock."""

from agents.base import make_agent
from models import AgentSpec

SPEC = AgentSpec(
    name="Inventory",
    emoji="📦",
    role="Checks stock by SKU and size, spots shortfalls, and figures out which vendor can restock.",
    prompt_file="inventory.md",
    tools=("get_today", "check_stock", "get_pricing", "list_vendors", "get_invoice_status", "list_purchase_orders", "add_ticket_note"),
)

agent = make_agent(SPEC)
