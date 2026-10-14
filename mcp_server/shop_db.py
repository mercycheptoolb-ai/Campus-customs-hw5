"""Campus Customs shop database — every read and write the MCP server exposes.

All shop rules live here so they hold no matter who calls:
  * "today" is desk.date_today, never the wall clock
  * a vendor with an open (unpaid) invoice will not ship — purchase orders are refused
  * money only moves through pay(), and pay() only runs an approval a human approved
  * pay() refuses if cash would go negative; cash only goes out
  * customer messages are drafts that stay on the board — nothing is sent

The original database (campus_customs.db) is never opened for writing. Everything
reads/writes the working copy (campus_customs_new.db); reset_working_copy() restores it.
"""

from __future__ import annotations

import calendar
import os
import shutil
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
ORIGINAL_DB = DATA_DIR / "campus_customs.db"
WORKING_DB = Path(os.getenv("SHOP_DB", DATA_DIR / "campus_customs_new.db"))

AGENTS = ("Boss", "Inventory", "Accounting", "Facilities", "Customer Service")
TICKET_STATUSES = ("open", "in_progress", "awaiting_approval", "blocked", "resolved")
CASH_ACCOUNT = "checking"

# Tables the original database does not have. They live only in the working copy and are
# rebuilt after every reset.
EXTRA_SCHEMA = """
CREATE TABLE IF NOT EXISTS approvals (
    id INTEGER PRIMARY KEY,
    ticket_id INTEGER,
    kind TEXT NOT NULL,            -- invoice_payment | rent_payment | purchase_order | price_override
    ref_id INTEGER,                -- invoice id / lease id / purchase order id
    amount REAL NOT NULL DEFAULT 0,
    summary TEXT NOT NULL,
    details TEXT,
    requested_by TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',   -- pending | approved | rejected | paid | refused
    decided_by TEXT,
    decided_at TEXT,
    result TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS purchase_orders (
    id INTEGER PRIMARY KEY,
    ticket_id INTEGER,
    vendor_id INTEGER NOT NULL,
    sku TEXT NOT NULL,
    size TEXT NOT NULL,
    qty INTEGER NOT NULL,
    unit_cost REAL NOT NULL,
    total REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',      -- draft | ordered | cancelled
    expected_date TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS drafts (
    id INTEGER PRIMARY KEY,
    ticket_id INTEGER,
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    author TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',      -- drafts are never sent
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ticket_log (
    id INTEGER PRIMARY KEY,
    ticket_id INTEGER NOT NULL,
    author TEXT NOT NULL,
    note TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


class ShopError(ValueError):
    """A rule was broken; the message is safe to show to an agent or a human."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    if not WORKING_DB.exists():
        reset_working_copy()
    conn = sqlite3.connect(WORKING_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        conn.executescript(EXTRA_SCHEMA)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _rows(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict]:
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def _one(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> dict | None:
    row = conn.execute(sql, params).fetchone()
    return dict(row) if row else None


def reset_working_copy() -> dict:
    """Overwrite the working copy with the untouched original database."""
    if not ORIGINAL_DB.exists():
        raise ShopError(f"Original database not found at {ORIGINAL_DB}")
    for suffix in ("-wal", "-shm", "-journal"):
        Path(str(WORKING_DB) + suffix).unlink(missing_ok=True)
    shutil.copyfile(ORIGINAL_DB, WORKING_DB)
    return {"reset": True, "working_db": WORKING_DB.name, "from": ORIGINAL_DB.name}


# ---------------------------------------------------------------- dates


def today(conn: sqlite3.Connection | None = None) -> date:
    if conn is None:
        with connect() as c:
            return today(c)
    row = _one(conn, "SELECT date_today FROM desk LIMIT 1")
    if not row:
        raise ShopError("desk.date_today is missing")
    return date.fromisoformat(row["date_today"][:10])


def _add_month(d: date) -> date:
    year, month = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


# ---------------------------------------------------------------- reads


def get_desk() -> dict:
    with connect() as c:
        desk = _one(c, "SELECT * FROM desk LIMIT 1") or {}
        return {**desk, "today": today(c).isoformat()}


def list_tickets(status: str | None = None) -> list[dict]:
    with connect() as c:
        if status:
            return _rows(c, "SELECT * FROM tickets WHERE status = ? ORDER BY id", (status,))
        return _rows(c, "SELECT * FROM tickets ORDER BY id")


def get_ticket(ticket_id: int) -> dict:
    with connect() as c:
        t = _one(c, "SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        if not t:
            raise ShopError(f"Ticket {ticket_id} not found")
        t["log"] = _rows(c, "SELECT author, note, created_at FROM ticket_log WHERE ticket_id = ? ORDER BY id", (ticket_id,))
        t["approvals"] = _rows(c, "SELECT * FROM approvals WHERE ticket_id = ? ORDER BY id", (ticket_id,))
        t["drafts"] = _rows(c, "SELECT * FROM drafts WHERE ticket_id = ? ORDER BY id", (ticket_id,))
        return t


def get_pricing(sku: str) -> dict:
    with connect() as c:
        p = _one(c, "SELECT * FROM pricing WHERE sku = ?", (sku,))
        if not p:
            raise ShopError(f"No pricing for sku={sku}")
        p["unit_margin"] = round(p["list_price"] - p["unit_cost"], 2)
        p["margin_pct"] = round(100 * p["unit_margin"] / p["list_price"], 1)
        return p


def check_margin(sku: str, qty: int, unit_price: float) -> dict:
    """Margin of selling `qty` units of `sku` at `unit_price` (e.g. a discounted price)."""
    p = get_pricing(sku)
    revenue, cost = unit_price * qty, p["unit_cost"] * qty
    return {
        "sku": sku,
        "qty": qty,
        "unit_price": unit_price,
        "list_price": p["list_price"],
        "unit_cost": p["unit_cost"],
        "discount_pct_vs_list": round(100 * (1 - unit_price / p["list_price"]), 1),
        "revenue": round(revenue, 2),
        "cost": round(cost, 2),
        "gross_margin": round(revenue - cost, 2),
        "margin_pct": round(100 * (revenue - cost) / revenue, 1) if revenue else None,
        "below_cost": unit_price < p["unit_cost"],
    }


def _invoice_view(inv: dict, today_: date) -> dict:
    due = date.fromisoformat(inv["due_date"][:10])
    is_open = inv["status"] != "paid"
    inv["days_overdue"] = max((today_ - due).days, 0) if is_open else 0
    inv["overdue"] = is_open and today_ > due
    return inv


def list_invoices(status: str | None = None, vendor_id: int | None = None) -> list[dict]:
    with connect() as c:
        t = today(c)
        sql, params = "SELECT i.*, v.name AS vendor_name FROM invoices i JOIN vendors v ON v.id = i.vendor_id WHERE 1=1", []
        if status:
            sql += " AND i.status = ?"
            params.append(status)
        if vendor_id is not None:
            sql += " AND i.vendor_id = ?"
            params.append(vendor_id)
        return [_invoice_view(r, t) for r in _rows(c, sql + " ORDER BY i.id", tuple(params))]


def _open_invoices(c: sqlite3.Connection, vendor_id: int) -> list[dict]:
    return _rows(c, "SELECT * FROM invoices WHERE vendor_id = ? AND status != 'paid'", (vendor_id,))


def list_vendors() -> list[dict]:
    with connect() as c:
        t = today(c)
        out = []
        for v in _rows(c, "SELECT * FROM vendors ORDER BY id"):
            blocking = _open_invoices(c, v["id"])
            out.append(
                {
                    **v,
                    "earliest_arrival_if_ordered_today": (t + timedelta(days=v["lead_days"])).isoformat(),
                    "will_ship": not blocking,
                    "blocking_invoice_ids": [i["id"] for i in blocking],
                    "open_balance": round(sum(i["amount"] for i in blocking), 2),
                }
            )
        return out


def get_cash() -> dict:
    with connect() as c:
        accounts = _rows(c, "SELECT * FROM cash_accounts ORDER BY name")
        pending = _one(c, "SELECT COALESCE(SUM(amount),0) AS s, COUNT(*) AS n FROM approvals WHERE status IN ('pending','approved') AND amount > 0")
        total = sum(a["balance"] for a in accounts)
        return {
            "today": today(c).isoformat(),
            "accounts": accounts,
            "total_cash": round(total, 2),
            "pending_approval_count": pending["n"],
            "pending_approval_amount": round(pending["s"], 2),
            "cash_after_pending": round(total - pending["s"], 2),
            "note": "Cash only goes out in this shop model — no revenue comes in.",
        }


def list_leases() -> list[dict]:
    with connect() as c:
        t = today(c)
        out = []
        for l in _rows(c, "SELECT * FROM leases ORDER BY id"):
            due = date.fromisoformat(l["next_due"][:10])
            out.append({**l, "days_until_due": (due - t).days, "overdue": t > due})
        return out


def list_payments() -> list[dict]:
    with connect() as c:
        return _rows(c, "SELECT * FROM payments ORDER BY id")


def list_approvals(status: str | None = None) -> list[dict]:
    with connect() as c:
        if status:
            return _rows(c, "SELECT * FROM approvals WHERE status = ? ORDER BY id", (status,))
        return _rows(c, "SELECT * FROM approvals ORDER BY id")


def list_drafts(ticket_id: int | None = None) -> list[dict]:
    with connect() as c:
        if ticket_id is not None:
            return _rows(c, "SELECT * FROM drafts WHERE ticket_id = ? ORDER BY id", (ticket_id,))
        return _rows(c, "SELECT * FROM drafts ORDER BY id")


def list_purchase_orders() -> list[dict]:
    with connect() as c:
        return _rows(
            c,
            "SELECT p.*, v.name AS vendor_name FROM purchase_orders p JOIN vendors v ON v.id = p.vendor_id ORDER BY p.id",
        )


def snapshot() -> dict:
    """Everything the dashboard shows, in one call."""
    with connect() as c:
        tickets = _rows(c, "SELECT * FROM tickets ORDER BY id")
        for t in tickets:
            t["log"] = _rows(c, "SELECT author, note, created_at FROM ticket_log WHERE ticket_id = ? ORDER BY id", (t["id"],))
        return {
            "desk": _one(c, "SELECT * FROM desk LIMIT 1"),
            "tickets": tickets,
            "inventory": _rows(c, "SELECT * FROM inventory ORDER BY sku, rowid"),
            "pricing": _rows(c, "SELECT * FROM pricing ORDER BY sku"),
            "cash_accounts": _rows(c, "SELECT * FROM cash_accounts"),
            "payments": _rows(c, "SELECT * FROM payments ORDER BY id"),
            "approvals": _rows(c, "SELECT * FROM approvals ORDER BY id"),
            "purchase_orders": _rows(c, "SELECT * FROM purchase_orders ORDER BY id"),
            "drafts": _rows(c, "SELECT * FROM drafts ORDER BY id"),
        } | {
            "invoices": list_invoices(),
            "leases": list_leases(),
            "vendors": list_vendors(),
        }


# ---------------------------------------------------------------- agent writes (no money moves)


def _check_ticket(c: sqlite3.Connection, ticket_id: int | None) -> None:
    if ticket_id is not None and not _one(c, "SELECT id FROM tickets WHERE id = ?", (ticket_id,)):
        raise ShopError(f"Ticket {ticket_id} not found")


def _check_agent(name: str) -> str:
    if name not in AGENTS:
        raise ShopError(f"Unknown agent '{name}'. Use one of: {', '.join(AGENTS)}")
    return name


def _duplicate(c: sqlite3.Connection, kind: str, ref_id: int | None) -> dict | None:
    return _one(
        c,
        "SELECT * FROM approvals WHERE kind = ? AND ref_id IS ? AND status IN ('pending','approved','paid')",
        (kind, ref_id),
    )


def add_ticket_note(ticket_id: int, author: str, note: str) -> dict:
    with connect() as c:
        _check_ticket(c, ticket_id)
        c.execute(
            "INSERT INTO ticket_log (ticket_id, author, note, created_at) VALUES (?,?,?,?)",
            (ticket_id, _check_agent(author), note.strip(), _now()),
        )
        return {"ok": True, "ticket_id": ticket_id}


def update_ticket_status(ticket_id: int, status: str, resolution: str) -> dict:
    if status not in TICKET_STATUSES:
        raise ShopError(f"status must be one of {TICKET_STATUSES}")
    with connect() as c:
        _check_ticket(c, ticket_id)
        c.execute("UPDATE tickets SET status = ? WHERE id = ?", (status, ticket_id))
        c.execute(
            "INSERT INTO ticket_log (ticket_id, author, note, created_at) VALUES (?,?,?,?)",
            (ticket_id, "Boss", f"[{status}] {resolution.strip()}", _now()),
        )
        return {"ok": True, "ticket_id": ticket_id, "status": status}


def request_invoice_payment(invoice_id: int, requested_by: str, reason: str, ticket_id: int | None = None) -> dict:
    """Queue an invoice payment for human approval. Nothing is paid here."""
    with connect() as c:
        _check_ticket(c, ticket_id)
        inv = _one(c, "SELECT i.*, v.name AS vendor_name FROM invoices i JOIN vendors v ON v.id = i.vendor_id WHERE i.id = ?", (invoice_id,))
        if not inv:
            raise ShopError(f"Invoice {invoice_id} not found")
        if inv["status"] == "paid":
            raise ShopError(f"Invoice {invoice_id} is already paid")
        if dup := _duplicate(c, "invoice_payment", invoice_id):
            return {"ok": True, "already_requested": True, "approval": dup}
        inv = _invoice_view(inv, today(c))
        summary = f"Pay invoice #{invoice_id} to {inv['vendor_name']} — ${inv['amount']:,.2f}"
        details = f"{inv['description'] or ''}. Due {inv['due_date']}" + (
            f", {inv['days_overdue']} days overdue." if inv["overdue"] else "."
        ) + f" Reason: {reason.strip()}"
        return _insert_approval(c, ticket_id, "invoice_payment", invoice_id, inv["amount"], summary, details, requested_by)


def request_rent_payment(lease_id: int, requested_by: str, reason: str, ticket_id: int | None = None) -> dict:
    """Queue the next rent payment on a lease for human approval. Nothing is paid here."""
    with connect() as c:
        _check_ticket(c, ticket_id)
        lease = _one(c, "SELECT * FROM leases WHERE id = ?", (lease_id,))
        if not lease:
            raise ShopError(f"Lease {lease_id} not found")
        if dup := _duplicate(c, "rent_payment", lease_id):
            return {"ok": True, "already_requested": True, "approval": dup}
        summary = f"Pay rent for {lease['space_name']} to {lease['landlord']} — ${lease['monthly_rent']:,.2f}"
        details = f"Rent due {lease['next_due']}. Reason: {reason.strip()}"
        return _insert_approval(c, ticket_id, "rent_payment", lease_id, lease["monthly_rent"], summary, details, requested_by)


def request_purchase_order(
    vendor_id: int, sku: str, size: str, qty: int, requested_by: str, reason: str, ticket_id: int | None = None
) -> dict:
    """Draft a purchase order (paid up front on approval) and queue it for human approval."""
    if qty <= 0:
        raise ShopError("qty must be positive")
    with connect() as c:
        _check_ticket(c, ticket_id)
        vendor = _one(c, "SELECT * FROM vendors WHERE id = ?", (vendor_id,))
        if not vendor:
            raise ShopError(f"Vendor {vendor_id} not found")
        price = _one(c, "SELECT * FROM pricing WHERE sku = ?", (sku,))
        if not price:
            raise ShopError(f"No pricing for sku={sku}")
        if not _one(c, "SELECT 1 FROM inventory WHERE sku = ? AND size = ?", (sku, size)):
            raise ShopError(f"No inventory line for sku={sku} size={size}")
        dup = _one(
            c,
            "SELECT a.* FROM approvals a JOIN purchase_orders p ON p.id = a.ref_id WHERE a.kind = 'purchase_order'"
            " AND a.status IN ('pending','approved') AND p.vendor_id = ? AND p.sku = ? AND p.size = ? AND p.ticket_id IS ?",
            (vendor_id, sku, size, ticket_id),
        )
        if dup:
            return {"ok": True, "already_requested": True, "approval": dup}
        total = round(price["unit_cost"] * qty, 2)
        eta = (today(c) + timedelta(days=vendor["lead_days"])).isoformat()
        cur = c.execute(
            "INSERT INTO purchase_orders (ticket_id, vendor_id, sku, size, qty, unit_cost, total, status, expected_date, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (ticket_id, vendor_id, sku, size, qty, price["unit_cost"], total, "draft", eta, _now()),
        )
        po_id = cur.lastrowid
        blocking = _open_invoices(c, vendor_id)
        summary = f"Purchase order #{po_id}: {qty} × {sku} ({size}) from {vendor['name']} — ${total:,.2f}"
        details = (
            f"Unit cost ${price['unit_cost']:.2f}. Lead time {vendor['lead_days']} days → arrives about {eta} if ordered today."
            + (
                f" BLOCKED until open invoice(s) {[i['id'] for i in blocking]} are paid — the vendor will not ship."
                if blocking
                else ""
            )
            + f" Reason: {reason.strip()}"
        )
        out = _insert_approval(c, ticket_id, "purchase_order", po_id, total, summary, details, requested_by)
        out["vendor_blocked_by_open_invoices"] = [i["id"] for i in blocking]
        return out


def request_price_override(
    ticket_id: int, sku: str, qty: int, unit_price: float, requested_by: str, reason: str
) -> dict:
    """Queue a discount / price override for human sign-off. Moves no money."""
    m = check_margin(sku, qty, unit_price)
    if m["below_cost"]:
        raise ShopError(f"${unit_price:.2f} is below unit cost ${m['unit_cost']:.2f}; the shop does not sell at a loss.")
    with connect() as c:
        _check_ticket(c, ticket_id)
        summary = (
            f"Price override for ticket #{ticket_id}: {qty} × {sku} at ${unit_price:.2f} "
            f"({m['discount_pct_vs_list']}% off ${m['list_price']:.2f})"
        )
        details = (
            f"Revenue ${m['revenue']:,.2f}, cost ${m['cost']:,.2f}, gross margin ${m['gross_margin']:,.2f} "
            f"({m['margin_pct']}%). Reason: {reason.strip()}"
        )
        return _insert_approval(c, ticket_id, "price_override", None, 0, summary, details, requested_by)


def _insert_approval(c, ticket_id, kind, ref_id, amount, summary, details, requested_by) -> dict:
    cur = c.execute(
        "INSERT INTO approvals (ticket_id, kind, ref_id, amount, summary, details, requested_by, status, created_at)"
        " VALUES (?,?,?,?,?,?,?, 'pending', ?)",
        (ticket_id, kind, ref_id, amount, summary, details, _check_agent(requested_by), _now()),
    )
    cash = _one(c, "SELECT balance FROM cash_accounts WHERE name = ?", (CASH_ACCOUNT,))
    return {
        "ok": True,
        "approval_id": cur.lastrowid,
        "status": "pending",
        "summary": summary,
        "message": "Queued for HUMAN approval on the dashboard. Nothing has been paid or committed.",
        "cash_now": cash["balance"] if cash else None,
    }


def draft_customer_message(ticket_id: int, recipient: str, subject: str, body: str, author: str = "Customer Service") -> dict:
    """Save a customer message draft on the board. Drafts are never sent."""
    with connect() as c:
        _check_ticket(c, ticket_id)
        cur = c.execute(
            "INSERT INTO drafts (ticket_id, recipient, subject, body, author, status, created_at) VALUES (?,?,?,?,?, 'draft', ?)",
            (ticket_id, recipient, subject, body.strip(), _check_agent(author), _now()),
        )
        return {"ok": True, "draft_id": cur.lastrowid, "status": "draft", "note": "Saved on the board. Not sent."}


# ---------------------------------------------------------------- human-only: decide + pay


def add_human_note(ticket_id: int, author: str, note: str) -> dict:
    """A human's instruction on a ticket (e.g. how to close it). Agents read it in get_ticket's log."""
    author = (author or "").strip()
    if not author or author in AGENTS:
        raise ShopError("A named human is required; agents cannot leave human notes.")
    if not note.strip():
        raise ShopError("The note is empty.")
    with connect() as c:
        _check_ticket(c, ticket_id)
        c.execute(
            "INSERT INTO ticket_log (ticket_id, author, note, created_at) VALUES (?,?,?,?)",
            (ticket_id, f"Human ({author})", note.strip(), _now()),
        )
        return {"ok": True, "ticket_id": ticket_id, "author": f"Human ({author})"}



def decide_approval(approval_id: int, decision: str, approver: str) -> dict:
    """A human approves or rejects a request. Approving a money request then runs pay()."""
    if decision not in ("approve", "reject"):
        raise ShopError("decision must be 'approve' or 'reject'")
    approver = (approver or "").strip()
    if not approver or approver in AGENTS:
        raise ShopError("A named human approver is required; agents cannot approve.")
    with connect() as c:
        a = _one(c, "SELECT * FROM approvals WHERE id = ?", (approval_id,))
        if not a:
            raise ShopError(f"Approval {approval_id} not found")
        if a["status"] != "pending":
            raise ShopError(f"Approval {approval_id} is already {a['status']}")
        status = "approved" if decision == "approve" else "rejected"
        result = None if status == "approved" else f"Rejected by {approver}"
        if a["kind"] == "price_override" and status == "approved":
            result = f"Price approved by {approver}"
        c.execute(
            "UPDATE approvals SET status = ?, decided_by = ?, decided_at = ?, result = ? WHERE id = ?",
            (status, approver, _now(), result, approval_id),
        )
        if a["kind"] == "purchase_order" and status == "rejected":
            c.execute("UPDATE purchase_orders SET status = 'cancelled' WHERE id = ?", (a["ref_id"],))
        if a["ticket_id"]:
            c.execute(
                "INSERT INTO ticket_log (ticket_id, author, note, created_at) VALUES (?,?,?,?)",
                (a["ticket_id"], "Boss", f"Human {approver} {status} request #{approval_id}: {a['summary']}", _now()),
            )
    if status == "approved" and a["kind"] != "price_override":
        return pay(approval_id)
    return {"ok": True, "approval_id": approval_id, "status": status, "result": result}


def pay(approval_id: int) -> dict:
    """Move money for a human-approved request, or refuse.

    Refuses when: the approval is not human-approved, cash would go negative, or (for a
    purchase order) the vendor still has an open unpaid invoice. On refusal nothing changes
    except the approval being marked 'refused' with the reason.
    """
    with connect() as c:
        a = _one(c, "SELECT * FROM approvals WHERE id = ?", (approval_id,))
        if not a:
            raise ShopError(f"Approval {approval_id} not found")
        if a["status"] != "approved" or not a["decided_by"] or a["decided_by"] in AGENTS:
            raise ShopError(f"Approval {approval_id} has not been approved by a human (status: {a['status']}). Refusing to pay.")
        if a["kind"] not in ("invoice_payment", "rent_payment", "purchase_order"):
            raise ShopError(f"Approval {approval_id} ({a['kind']}) is not a payment")

        t = today(c)
        cash = _one(c, "SELECT * FROM cash_accounts WHERE name = ?", (CASH_ACCOUNT,))
        amount = round(a["amount"], 2)

        def refuse(reason: str) -> dict:
            c.execute("UPDATE approvals SET status = 'refused', result = ? WHERE id = ?", (reason, approval_id))
            if a["kind"] == "purchase_order":
                c.execute("UPDATE purchase_orders SET status = 'cancelled' WHERE id = ?", (a["ref_id"],))
            if a["ticket_id"]:
                c.execute(
                    "INSERT INTO ticket_log (ticket_id, author, note, created_at) VALUES (?,?,?,?)",
                    (a["ticket_id"], "Accounting", f"Pay tool REFUSED request #{approval_id}: {reason}", _now()),
                )
            return {"ok": False, "approval_id": approval_id, "status": "refused", "reason": reason}

        if not cash:
            return refuse(f"No '{CASH_ACCOUNT}' cash account")
        if amount <= 0:
            return refuse("Amount must be positive")
        if cash["balance"] - amount < 0:
            return refuse(f"Not enough cash: balance ${cash['balance']:,.2f} < ${amount:,.2f}. No negative balances.")

        if a["kind"] == "invoice_payment":
            inv = _one(c, "SELECT * FROM invoices WHERE id = ?", (a["ref_id"],))
            if not inv or inv["status"] == "paid":
                return refuse(f"Invoice {a['ref_id']} is missing or already paid")
            c.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (inv["id"],))
            effect = f"Invoice #{inv['id']} marked paid"
            pay_kind = "invoice"
        elif a["kind"] == "rent_payment":
            lease = _one(c, "SELECT * FROM leases WHERE id = ?", (a["ref_id"],))
            if not lease:
                return refuse(f"Lease {a['ref_id']} not found")
            new_due = _add_month(date.fromisoformat(lease["next_due"][:10])).isoformat()
            c.execute("UPDATE leases SET next_due = ? WHERE id = ?", (new_due, lease["id"]))
            effect = f"Rent for {lease['next_due']} paid; lease next_due moved to {new_due}"
            pay_kind = "rent"
        else:
            po = _one(c, "SELECT * FROM purchase_orders WHERE id = ?", (a["ref_id"],))
            if not po or po["status"] != "draft":
                return refuse(f"Purchase order {a['ref_id']} is missing or not a draft")
            blocking = _open_invoices(c, po["vendor_id"])
            if blocking:
                return refuse(
                    f"Vendor {po['vendor_id']} still has open unpaid invoice(s) {[i['id'] for i in blocking]} and will not ship."
                )
            vendor = _one(c, "SELECT * FROM vendors WHERE id = ?", (po["vendor_id"],))
            eta = (t + timedelta(days=vendor["lead_days"])).isoformat()
            c.execute("UPDATE purchase_orders SET status = 'ordered', expected_date = ? WHERE id = ?", (eta, po["id"]))
            effect = f"PO #{po['id']} placed with {vendor['name']}; expected {eta}"
            pay_kind = "purchase_order"

        new_balance = round(cash["balance"] - amount, 2)
        c.execute(
            "UPDATE cash_accounts SET balance = ?, date = ? WHERE name = ?",
            (new_balance, t.isoformat(), CASH_ACCOUNT),
        )
        cur = c.execute(
            "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) VALUES (?,?,?,?,?,?)",
            (pay_kind, a["ref_id"], amount, CASH_ACCOUNT, t.isoformat(), a["decided_by"]),
        )
        result = f"Paid ${amount:,.2f} (payment #{cur.lastrowid}). {effect}. Cash now ${new_balance:,.2f}."
        c.execute("UPDATE approvals SET status = 'paid', result = ? WHERE id = ?", (result, approval_id))
        if a["ticket_id"]:
            c.execute(
                "INSERT INTO ticket_log (ticket_id, author, note, created_at) VALUES (?,?,?,?)",
                (a["ticket_id"], "Accounting", result, _now()),
            )
        return {"ok": True, "approval_id": approval_id, "status": "paid", "payment_id": cur.lastrowid, "result": result, "cash_balance": new_balance}
