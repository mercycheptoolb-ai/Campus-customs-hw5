"""Accounting — watches cash and invoices, checks margins, and prepares payments or purchase orders for human approval."""

from agents.base import make_agent
from models import AgentSpec

SPEC = AgentSpec(
    name="Accounting",
    emoji="💵",
    role="Watches cash and invoices, checks margins, and prepares payments or purchase orders for human approval.",
    prompt_file="accounting.md",
    tools=(
        "get_today",
        "get_cash",
        "get_invoice_status",
        "list_invoices",
        "get_rent_due",
        "list_vendors",
        "get_pricing",
        "check_margin",
        "list_approvals",
        "list_payments",
        "list_purchase_orders",
        "request_invoice_payment",
        "request_rent_payment",
        "request_purchase_order",
        "request_price_override",
        "add_ticket_note",
    ),
)

agent = make_agent(SPEC)
