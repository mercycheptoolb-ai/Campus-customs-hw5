"""Campus Customs MCP server (FastMCP).

The shared tool box for every agent on the Campus Customs team. It talks only to the
working copy data/campus_customs_new.db — the original data/campus_customs.db is only
read by admin_reset_database to restore the working copy. Tools return values exactly as
stored in the database (plus simple date math against desk.date_today); if a record is
missing they raise an error instead of guessing.

Problem 3 tools (read-only):
  check_stock(sku, size, needed_qty=None)  inventory          → tickets 101, 103
  get_invoice_status(invoice_id)           invoices, vendors  → ticket 101
  get_rent_due(lease_id)                   leases             → ticket 102

Problem 5 adds the reads, agent write tools, and human/admin tools the agent team needs.
The shop rules are enforced in shop_db.py so they hold no matter who calls. Agents only
get the tools their role allows (backend/agents/); human_* and admin_* tools are for the
dashboard's human operator and are never given to an agent.

Run (stdio):  .venv/bin/python mcp_server/server.py
"""

from __future__ import annotations

import functools
import sqlite3
import sys
from datetime import date
from pathlib import Path
from typing import Any, Callable

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

sys.path.insert(0, str(Path(__file__).resolve().parent))

import shop_db  # noqa: E402

DB_PATH = shop_db.WORKING_DB

mcp = FastMCP(
    name="campus-customs",
    instructions=(
        "Campus Customs shop tools over data/campus_customs_new.db. 'Today' is desk.date_today, "
        "not the real-world date. Every value comes from the database; nothing is estimated. "
        "Payments and purchase orders are only requested here; a human approves them. "
        "Customer messages are drafts that are never sent."
    ),
)


def connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise ToolError(f"Working database not found at {DB_PATH.name}. Copy data/campus_customs.db to it first.")
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)  # these tools only read
    conn.row_factory = sqlite3.Row
    return conn


def shop_today(conn: sqlite3.Connection) -> date:
    row = conn.execute("SELECT date_today FROM desk LIMIT 1").fetchone()
    if row is None:
        raise ToolError("desk.date_today is missing, so the shop's 'today' is unknown.")
    return date.fromisoformat(row["date_today"][:10])


@mcp.tool
def check_stock(sku: str, size: str, needed_qty: int | None = None) -> dict:
    """Units on hand for one product SKU in one size (from the inventory table).

    Pass needed_qty (e.g. the ticket's qty) to get the shortfall: how many more units
    the shop must restock to fill the request.
    """
    with connect() as conn:
        row = conn.execute(
            "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ? AND size = ?",
            (sku, size),
        ).fetchone()
        if row is None:
            sizes = [r["size"] for r in conn.execute("SELECT size FROM inventory WHERE sku = ?", (sku,))]
            hint = f" Sizes on file for {sku}: {', '.join(sizes)}." if sizes else f" SKU {sku} is not in inventory."
            raise ToolError(f"No inventory row for sku={sku} size={size}.{hint}")
        result = dict(row)
    if needed_qty is not None:
        result["needed_qty"] = needed_qty
        result["shortfall"] = max(needed_qty - result["qty"], 0)
        result["can_fill_from_stock"] = result["qty"] >= needed_qty
    return result


@mcp.tool
def get_invoice_status(invoice_id: int) -> dict:
    """One vendor invoice with its vendor, and whether it is open and overdue as of desk.date_today.

    An open (unpaid) invoice means that vendor will not ship new product until it is paid.
    """
    with connect() as conn:
        row = conn.execute(
            """
            SELECT i.id AS invoice_id, i.amount, i.due_date, i.status, i.description,
                   v.id AS vendor_id, v.name AS vendor_name, v.specialty AS vendor_specialty,
                   v.lead_days AS vendor_lead_days
            FROM invoices i JOIN vendors v ON v.id = i.vendor_id
            WHERE i.id = ?
            """,
            (invoice_id,),
        ).fetchone()
        if row is None:
            raise ToolError(f"Invoice {invoice_id} not found.")
        today = shop_today(conn)
    result = dict(row)
    is_open = result["status"] != "paid"
    days_past_due = (today - date.fromisoformat(result["due_date"][:10])).days
    result.update(
        shop_today=today.isoformat(),
        is_open=is_open,
        days_overdue=max(days_past_due, 0) if is_open else 0,
        overdue=is_open and days_past_due > 0,
        vendor_blocked=is_open,
    )
    return result


@mcp.tool
def get_rent_due(lease_id: int) -> dict:
    """Rent amount, landlord, and next due date for one lease, with days until due as of desk.date_today."""
    with connect() as conn:
        row = conn.execute(
            "SELECT id AS lease_id, space_name, landlord, monthly_rent, next_due, notes FROM leases WHERE id = ?",
            (lease_id,),
        ).fetchone()
        if row is None:
            raise ToolError(f"Lease {lease_id} not found.")
        today = shop_today(conn)
    result = dict(row)
    days_until_due = (date.fromisoformat(result["next_due"][:10]) - today).days
    result.update(shop_today=today.isoformat(), days_until_due=days_until_due, overdue=days_until_due < 0)
    return result


def shop_tool(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Register a shop_db-backed tool. A broken shop rule comes back as a ToolError the agent can read."""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except shop_db.ShopError as exc:
            raise ToolError(str(exc)) from exc

    mcp.tool(wrapper)
    return fn


# ---------------------------------------------------------------- Problem 5: reads


@shop_tool
def get_today() -> dict:
    """The shop's 'today' (desk.date_today) plus desk notes. Use this date for anything overdue or due soon."""
    return shop_db.get_desk()


@shop_tool
def list_tickets(status: str | None = None) -> list[dict]:
    """Tickets on the board. status: open | in_progress | awaiting_approval | blocked | resolved (omit for all)."""
    return shop_db.list_tickets(status)


@shop_tool
def get_ticket(ticket_id: int) -> dict:
    """One ticket with its work log, approval requests, and customer drafts."""
    return shop_db.get_ticket(ticket_id)


@shop_tool
def get_pricing(sku: str) -> dict:
    """Unit cost, list price, and unit margin for a SKU (pricing table)."""
    return shop_db.get_pricing(sku)


@shop_tool
def check_margin(sku: str, qty: int, unit_price: float) -> dict:
    """Revenue, cost, gross margin and discount % if `qty` of `sku` sell at `unit_price`; flags prices below unit cost."""
    return shop_db.check_margin(sku, qty, unit_price)


@shop_tool
def list_vendors() -> list[dict]:
    """Every vendor with specialty, lead_days, arrival date if ordered today, and whether it will ship.

    will_ship is false while the vendor has an open unpaid invoice (blocking_invoice_ids).
    """
    return shop_db.list_vendors()


@shop_tool
def list_invoices(status: str | None = None, vendor_id: int | None = None) -> list[dict]:
    """Vendor invoices with days_overdue computed from the shop's today. status: open | paid."""
    return shop_db.list_invoices(status, vendor_id)


@shop_tool
def get_cash() -> dict:
    """Cash balances, plus how much is already waiting on human approval (cash_after_pending)."""
    return shop_db.get_cash()


@shop_tool
def list_payments() -> list[dict]:
    """Payments already made (payments table): kind, ref_id, amount, account, paid_at, and the human who approved."""
    return shop_db.list_payments()


@shop_tool
def list_approvals(status: str | None = None) -> list[dict]:
    """Requests waiting on (or decided by) a human. status: pending | approved | rejected | paid | refused."""
    return shop_db.list_approvals(status)


@shop_tool
def list_drafts(ticket_id: int | None = None) -> list[dict]:
    """Customer message drafts on the board (never sent)."""
    return shop_db.list_drafts(ticket_id)


@shop_tool
def list_purchase_orders() -> list[dict]:
    """Restock purchase orders (draft / ordered / cancelled)."""
    return shop_db.list_purchase_orders()


# ---------------------------------------------------------------- Problem 5: agent writes (no money moves)


@shop_tool
def add_ticket_note(ticket_id: int, author: str, note: str) -> dict:
    """Add a work-log note to a ticket. author is your agent name."""
    return shop_db.add_ticket_note(ticket_id, author, note)


@shop_tool
def update_ticket_status(ticket_id: int, status: str, resolution: str) -> dict:
    """Boss only: set a ticket's status (open | in_progress | awaiting_approval | blocked | resolved) with the reason."""
    return shop_db.update_ticket_status(ticket_id, status, resolution)


@shop_tool
def request_invoice_payment(invoice_id: int, requested_by: str, reason: str, ticket_id: int | None = None) -> dict:
    """Queue a vendor invoice payment for HUMAN approval. Does not pay anything."""
    return shop_db.request_invoice_payment(invoice_id, requested_by, reason, ticket_id)


@shop_tool
def request_rent_payment(lease_id: int, requested_by: str, reason: str, ticket_id: int | None = None) -> dict:
    """Queue the next rent payment on a lease for HUMAN approval. Does not pay anything."""
    return shop_db.request_rent_payment(lease_id, requested_by, reason, ticket_id)


@shop_tool
def request_purchase_order(
    vendor_id: int, sku: str, size: str, qty: int, requested_by: str, reason: str, ticket_id: int | None = None
) -> dict:
    """Draft a restock purchase order and queue it for HUMAN approval. Paid up front only after approval."""
    return shop_db.request_purchase_order(vendor_id, sku, size, qty, requested_by, reason, ticket_id)


@shop_tool
def request_price_override(ticket_id: int, sku: str, qty: int, unit_price: float, requested_by: str, reason: str) -> dict:
    """Queue a discount / custom unit price for HUMAN sign-off. Refuses prices below unit cost."""
    return shop_db.request_price_override(ticket_id, sku, qty, unit_price, requested_by, reason)


@shop_tool
def draft_customer_message(ticket_id: int, recipient: str, subject: str, body: str, author: str = "Customer Service") -> dict:
    """Save a customer message as a DRAFT on the board. Nothing is ever emailed or sent."""
    return shop_db.draft_customer_message(ticket_id, recipient, subject, body, author)


# ---------------------------------------------------------------- human / admin tools (never given to agents)


@shop_tool
def human_decide_approval(approval_id: int, decision: str, approver: str) -> dict:
    """HUMAN ONLY. Approve or reject a pending request. Approving a payment or PO runs the pay tool."""
    return shop_db.decide_approval(approval_id, decision, approver)


@shop_tool
def human_add_ticket_note(ticket_id: int, author: str, note: str) -> dict:
    """HUMAN ONLY. Leave the human's decision or instruction on a ticket's log (e.g. how to close it).
    The Boss treats a Human note as the human's call."""
    return shop_db.add_human_note(ticket_id, author, note)


@shop_tool
def human_pay(approval_id: int) -> dict:
    """HUMAN ONLY. The pay tool: pays a human-approved request and updates invoices/leases/purchase_orders,
    cash_accounts and payments. Refuses if not human-approved, cash would go negative, or the vendor is blocked."""
    return shop_db.pay(approval_id)


@shop_tool
def admin_reset_database() -> dict:
    """ADMIN ONLY. Restore the working copy from the original campus_customs.db (done before every full run)."""
    return shop_db.reset_working_copy()


@shop_tool
def admin_snapshot() -> dict:
    """ADMIN ONLY. Every table the dashboard shows, in one call."""
    return shop_db.snapshot()


if __name__ == "__main__":
    mcp.run(show_banner=False)
