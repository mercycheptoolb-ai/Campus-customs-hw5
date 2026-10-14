# Campus Customs MCP server

**What it's for:** it's the one shared tool box for the Campus Customs agent team (Boss, Inventory, Accounting, Facilities, Customer Service). Agents don't query the database themselves. They call these tools, so every agent sees the same facts and the shop rules live in one place. The server is built with [FastMCP](https://gofastmcp.com) and talks over stdio.

**Database:** `data/campus_customs_new.db`, the working copy. The original `data/campus_customs.db` is only read by `admin_reset_database`, so the shop can always be reset by copying the original over the working copy. Every value a tool returns comes from the database. The only computed values are simple date math against the shop's "today" (`desk.date_today`) and shortfall math. If a record isn't there, the tool returns an error instead of guessing.

## Tools (27)

The shop rules live in `shop_db.py`, so they hold no matter who calls. If a call breaks a rule, the tool returns an error the agent can read. "R" = reads, "W" = writes.

### Read tools
| Tool | Tables | Returns |
|---|---|---|
| `check_stock(sku, size, needed_qty=None)` | R `inventory` | Units on hand for one SKU and size; with `needed_qty`, the shortfall and whether stock can fill it (Problem 3) |
| `get_invoice_status(invoice_id)` | R `invoices`, `vendors`, `desk` | One invoice with its vendor and lead time, days overdue, and whether the vendor is blocked from shipping (Problem 3) |
| `get_rent_due(lease_id)` | R `leases`, `desk` | Rent amount, landlord, next due date, days until due (Problem 3) |
| `get_today()` | R `desk` | The shop's "today" |
| `list_tickets(status=None)` | R `tickets` | Tickets on the board |
| `get_ticket(ticket_id)` | R `tickets`, `ticket_log`, `approvals`, `drafts` | One ticket with its work log, requests and drafts |
| `get_pricing(sku)` | R `pricing` | Unit cost, list price, unit margin |
| `check_margin(sku, qty, unit_price)` | R `pricing` | Revenue, cost, margin and discount at a proposed price; flags prices below cost |
| `list_vendors()` | R `vendors`, `invoices`, `desk` | Specialty, lead days, arrival date if ordered today, whether the vendor will ship, and blocking invoices |
| `list_invoices(status=None, vendor_id=None)` | R `invoices`, `vendors`, `desk` | Invoices with days overdue |
| `get_cash()` | R `cash_accounts`, `approvals`, `desk` | Balances, the total waiting on approval, and cash left after pending requests |
| `list_payments()` | R `payments` | Payments already made and who approved them |
| `list_approvals(status=None)` | R `approvals` | Requests waiting on or decided by a human |
| `list_drafts(ticket_id=None)` | R `drafts` | Customer message drafts |
| `list_purchase_orders()` | R `purchase_orders`, `vendors` | Restock POs (draft, ordered or cancelled) |

### Agent write tools (no money moves)
| Tool | Tables | What it does |
|---|---|---|
| `add_ticket_note(ticket_id, author, note)` | W `ticket_log` | Adds a note to the ticket's work log |
| `update_ticket_status(ticket_id, status, resolution)` | W `tickets`, `ticket_log` | Sets the ticket status (Boss only) |
| `request_invoice_payment(invoice_id, requested_by, reason, ticket_id)` | R `invoices`, `vendors`; W `approvals` | Queues an invoice payment for human approval |
| `request_rent_payment(lease_id, requested_by, reason, ticket_id)` | R `leases`; W `approvals` | Queues a rent payment for human approval |
| `request_purchase_order(vendor_id, sku, size, qty, requested_by, reason, ticket_id)` | R `vendors`, `pricing`, `inventory`, `invoices`; W `purchase_orders`, `approvals` | Drafts a PO and queues it for human approval; warns if the vendor is blocked |
| `request_price_override(ticket_id, sku, qty, unit_price, requested_by, reason)` | R `pricing`; W `approvals` | Queues a discount for human sign-off; refuses prices below unit cost |
| `draft_customer_message(ticket_id, recipient, subject, body)` | W `drafts` | Saves a draft. Nothing is sent |

### Human / admin tools (never given to an agent)
| Tool | Tables | What it does |
|---|---|---|
| `human_decide_approval(approval_id, decision, approver)` | W `approvals`, `purchase_orders`, `ticket_log` | A named human approves or rejects a request. Approving a money request runs the pay tool |
| `human_add_ticket_note(ticket_id, author, note)` | W `ticket_log` | A named human leaves a decision on a ticket (e.g. how to close it). The Boss follows it (added in Problem 9) |
| `human_pay(approval_id)` | W `cash_accounts`, `payments`, `invoices` / `leases` / `purchase_orders`, `approvals` | **The pay tool.** Pays only a human-approved request and updates the related tables. Refuses if cash would go negative or the vendor has an open invoice |
| `admin_reset_database()` | Whole file | Copies `campus_customs.db` over the working copy (before every full run) |
| `admin_snapshot()` | Every table | Everything the dashboard shows |

The working copy also gets four tables the original doesn't have: `approvals`, `purchase_orders`, `drafts` and `ticket_log`. They're rebuilt after every reset.

## Run

```bash
.venv/bin/python mcp_server/server.py      # stdio MCP server (the backend also starts it for you)
```
