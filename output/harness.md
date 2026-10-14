# Campus Customs Agent Harness

The operating contract for the Campus Customs multi-agent team (Boss, Inventory, Accounting, Facilities, Customer Service). This file grows with each problem.

- **Original database:** `data/campus_customs.db`. Read-only, kept so the shop can be reset.
- **Working copy:** `data/campus_customs_new.db`. The MCP server and backend read and write only this file.

**Contents:**
1. Database tables
2. How the tickets link
3. Problem 3 MCP tools
4. The five agents
5. MCP tool catalog (27)
6. Audit trail
7. Safety: shop rules, guardrails, token limits
8. API routes
9. Dashboard
10. Problem 9: the resolved run

---

## 1. Database tables

The original database has nine tables. PK = primary key, FK = foreign key.

### desk
| Field | Type | Notes |
|---|---|---|
| date_today | TEXT, required | The shop's "today" (2026-08-31) |
| notes | TEXT | Desk notes (empty) |

**Why it matters:** Every agent must use `date_today` as "today" to judge what is overdue or due soon. They must not use the real-world date.

### tickets
| Field | Type | Notes |
|---|---|---|
| id | INTEGER PK | Ticket number (101–103) |
| type | TEXT, required | `customer_order`, `rent_notice`, `price_override` |
| requester | TEXT, required | Who raised it (customer, landlord, student org) |
| subject | TEXT, required | Short title |
| sku | TEXT | Product involved → `inventory.sku`, `pricing.sku` |
| size | TEXT | Size involved → `inventory.size` |
| qty | INTEGER | Units requested |
| lease_id | INTEGER FK → `leases.id` | Set on rent tickets |
| invoice_id | INTEGER FK → `invoices.id` | Set when a vendor bill is involved |
| status | TEXT, required | `open` at start |
| notes | TEXT | Free-text request details |
| created_at | TEXT, required | ISO timestamp |

**Why it matters:** This is the work queue. The Boss reads each ticket and routes it, and the ticket's `sku`, `lease_id` and `invoice_id` columns point the agents to the other tables they need.

### inventory
| Field | Type | Notes |
|---|---|---|
| sku | TEXT, PK (with size) | Product code |
| name | TEXT, required | Product name |
| size | TEXT, PK (with sku) | S / M / L / XL, or OS (one size) |
| qty | INTEGER, required | Units on hand |
| location | TEXT, required | Aisle |

**Why it matters:** Inventory checks stock for an exact SKU and size to find shortfalls (for example, tee size S = 0).

### pricing
| Field | Type | Notes |
|---|---|---|
| sku | TEXT PK | Product code |
| unit_cost | REAL, required | What the shop pays per unit |
| list_price | REAL, required | Normal selling price |

**Why it matters:** Accounting uses it to check margins on discount requests (never below `unit_cost`) and to price purchase orders.

### vendors
| Field | Type | Notes |
|---|---|---|
| id | INTEGER PK | Vendor id |
| name | TEXT, required | Bulldog Print Co, Elm City Gifts, QuickShip CT |
| specialty | TEXT, required | What they supply (apparel reprint, mugs and small goods, local courier) |
| lead_days | INTEGER, required | Days from order to arrival |

**Why it matters:** Inventory picks the restock vendor by `specialty` and estimates arrival as today + `lead_days`.

### leases
| Field | Type | Notes |
|---|---|---|
| id | INTEGER PK | Lease id |
| space_name | TEXT, required | Chapel Street shop |
| landlord | TEXT, required | Elm City Properties |
| monthly_rent | REAL, required | $2,400 |
| next_due | TEXT, required | Next rent date (2026-09-02) |
| notes | TEXT | Lease notes |

**Why it matters:** Facilities uses it to confirm the rent amount, landlord and due date before asking Accounting to queue the rent payment.

### cash_accounts
| Field | Type | Notes |
|---|---|---|
| name | TEXT PK | `checking` |
| balance | REAL, required | $3,400 at start |
| date | TEXT, required | As-of date of the balance |

**Why it matters:** This is the only source of money, and cash only goes out. Accounting checks it before preparing payments, and the pay tool must refuse any payment that would make it negative.

### payments
| Field | Type | Notes |
|---|---|---|
| id | INTEGER PK | Payment id |
| kind | TEXT, required | What was paid (invoice, rent, purchase order) |
| ref_id | INTEGER | Id of the invoice, lease or purchase order paid |
| amount | REAL, required | Amount paid |
| account | TEXT, required | Cash account debited |
| paid_at | TEXT, required | Date paid (shop date) |
| approved_by | TEXT, required | The human who approved it |

**Why it matters:** It is the audit trail of money out. It starts empty, and a row is written only after a human approves. `approved_by` must be a person, never an agent.

### invoices
| Field | Type | Notes |
|---|---|---|
| id | INTEGER PK | Invoice id |
| vendor_id | INTEGER FK → `vendors.id` | Who billed the shop |
| amount | REAL, required | Amount owed |
| due_date | TEXT, required | When it was due |
| status | TEXT, required | `open` or `paid` |
| description | TEXT | What the bill is for |

**Why it matters:** An open invoice means the vendor will not ship new product. Accounting must get it paid (with human approval) before any restock from that vendor.

### Working-copy tables (added by the MCP server)
The original database has no place to park a request while it waits for a human, so the MCP server (`mcp_server/shop_db.py`) adds four tables to the **working copy only**. A reset deletes them, and they're rebuilt on first use.

| Table | Fields | Why it matters for the agents |
|---|---|---|
| `approvals` | id, ticket_id, kind (`invoice_payment` / `rent_payment` / `purchase_order` / `price_override`), ref_id, amount, summary, details, requested_by (agent), status (`pending` / `approved` / `rejected` / `paid` / `refused`), decided_by (human), decided_at, result, created_at | The human-approval gate. Agents write `pending` rows; only a human moves them on, and only an approved row can be paid |
| `purchase_orders` | id, ticket_id, vendor_id, sku, size, qty, unit_cost, total, status (`draft` / `ordered` / `cancelled`), expected_date, created_at | Restock orders. A PO stays a draft until a human approves it and the pay tool places it |
| `drafts` | id, ticket_id, recipient, subject, body, author, status (always `draft`), created_at | Customer messages. They stay on the board and are never sent |
| `ticket_log` | id, ticket_id, author, note, created_at | Each ticket's work log: agent notes, status changes, approval results, and **human notes** (author `Human (…)`) that the Boss must follow |

---

## 2. How the three open tickets link to the other tables

```
tickets ──invoice_id──▶ invoices ──vendor_id──▶ vendors
   │  └──lease_id────▶ leases
   └──sku, size──────▶ inventory, pricing
desk.date_today ── decides what is overdue
cash_accounts ◀── payments (every payment draws on checking)
```

### #101 — customer_order: "Bulldog tee" (Tauhid Zaman)
- **Wants:** `CC-TEE-WHITE`, size S, qty 1, `invoice_id` = 501.
- **inventory:** the tee in size S has qty **0**, a shortfall of 1.
- **invoices → vendors:** invoice 501 is the "Rush reprint CC-TEE-WHITE S" bill from vendor 1, Bulldog Print Co: $840, due 2026-08-28, status **open**. It is **3 days overdue** against `desk.date_today`.
- **vendors:** Bulldog Print Co (apparel reprint) can restock, with a lead time of 5 days (arriving about 2026-09-05). But it won't ship while invoice 501 is unpaid.
- **pricing:** the tee costs $8.00 and sells for $28.00.
- **Agents involved:** Inventory (stock and vendor), Accounting (pay invoice 501, then a purchase order), Customer Service (a draft to the customer), Boss (final call).

### #102 — rent_notice: "Rent due" (Elm City Properties)
- **Wants:** `lease_id` = 1. The note says "shop rent due in 2 days".
- **leases:** Chapel Street shop, rent $2,400, `next_due` 2026-09-02. That is 2 days after 2026-08-31, so due soon but not yet overdue.
- **cash_accounts:** $3,400 in checking covers it.
- **Effect of paying (after human approval):** a `payments` row (rent), checking drops by $2,400, and `leases.next_due` moves forward one month.
- **Agents involved:** Facilities (lease), Accounting (queue the payment), Boss.

### #103 — price_override: "Bulk hoodie discount" (Yale AI Club)
- **Wants:** `CC-HOOD-NAVY`, size M, qty 20, with a bulk discount.
- **inventory:** size M has qty **8**, a shortfall of 12.
- **pricing:** the hoodie costs $22.00 and lists at $58.00. Any discount must stay above $22.
- **vendors / invoices:** the restock vendor is Bulldog Print Co again (5-day lead), which is **blocked by the same open invoice 501**.
- **cash_accounts:** 12 more hoodies would cost 12 × $22 = $264. After the $840 invoice and $2,400 rent, only $160 is left, so the restock does not fit.
- **Agents involved:** Inventory (shortfall and vendor), Accounting (margin, discount and purchase order), Customer Service (a draft to the club), Boss.

### Cross-ticket takeaways
- **Invoice 501 is the shared blocker.** It holds up both the #101 tee restock and the #103 hoodie restock.
- **Cash is tight.** $3,400 covers $840 + $2,400 = $3,240, leaving $160 (and $152 once the $8 tee PO is paid). That is not enough for the $264 hoodie restock, so the Boss has to put the tickets in priority order.
- **Every money step needs a human.** That covers the invoice payment, the rent, any purchase order and the discount sign-off.

---

## 3. MCP tools

All agents get their tools from one FastMCP server, `mcp_server/server.py`, which reads the working copy `data/campus_customs_new.db`. The tools only read the database, and they return its values as stored. If a SKU, invoice or lease isn't there, the tool returns an error rather than inventing a value. "Today" always comes from `desk.date_today` (2026-08-31).

### `check_stock(sku, size, needed_qty=None)`
- **Reads:** `inventory` (`sku`, `name`, `size`, `qty`, `location`), matched on the exact SKU and size.
- **Unlocks:** ticket **101** (`CC-TEE-WHITE`, size S, qty 1) and ticket **103** (`CC-HOOD-NAVY`, size M, qty 20).
- **Why it's the right tool:** both tickets ask for an exact SKU, size and quantity. Called with the ticket's `qty` as `needed_qty`, it shows that #101 has 0 tees in S (short 1) and #103 has only 8 hoodies in M (short 12). Those shortfalls are what make a restock necessary.

### `get_invoice_status(invoice_id)`
- **Reads:** `invoices` (`amount`, `due_date`, `status`, `description`), joined to `vendors` (`name`, `specialty`, `lead_days`) through `vendor_id`, plus `desk.date_today`.
- **Unlocks:** ticket **101**, which carries `invoice_id` = 501.
- **Why it's the right tool:** the tee can't be restocked until invoice 501 is dealt with. The tool shows it is Bulldog Print Co's $840 "Rush reprint CC-TEE-WHITE S" bill, still open and 3 days overdue. An open invoice means the vendor won't ship, and the same block also stops the #103 hoodie restock.

### `get_rent_due(lease_id)`
- **Reads:** `leases` (`space_name`, `landlord`, `monthly_rent`, `next_due`, `notes`), plus `desk.date_today`.
- **Unlocks:** ticket **102**, which carries `lease_id` = 1.
- **Why it's the right tool:** the landlord's email only says rent is "due in 2 days". This tool checks that claim against the lease: $2,400 to Elm City Properties for the Chapel Street shop, due 2026-09-02, which is 2 days after the shop's today. That gives Facilities and Accounting the exact amount and date to put in front of the human for approval.

---

## 4. Agent team (Problem 5)

Five PydanticAI agents, all on `gpt-6-luna` through Portkey (`backend/agents/config.py`, the only place a model is named). Each agent is one file in `backend/agents/` with its prompt in `backend/prompts/<agent>.md`, plus the shared shop rules in `backend/prompts/shared_rules.md`. Data types are in `backend/models.py`.

Every agent also has `delegate(to_agent, task)`, a backend tool rather than an MCP tool, so any agent can hand work to any other one (full connectivity). Agents read and change shop data **only through the MCP tools** below. The backend never opens the database itself.

| Agent | Assignment | MCP tools | Tables it reads / writes (through those tools) | Output |
|---|---|---|---|---|
| **Boss** | Reads each ticket, decides who should work on it, makes the final call | `get_today`, `get_ticket`, `list_tickets`, `get_cash`, `list_approvals`, `list_payments`, `add_ticket_note`, `update_ticket_status` | reads `desk`, `tickets`, `ticket_log`, `approvals`, `drafts`, `cash_accounts`, `payments`; writes `tickets.status`, `ticket_log` | `BossDecision` |
| **Inventory** | Checks stock by SKU and size, spots shortfalls, finds which vendor can restock | `get_today`, `check_stock`, `get_pricing`, `list_vendors`, `get_invoice_status`, `list_purchase_orders`, `add_ticket_note` | reads `desk`, `inventory`, `pricing`, `vendors`, `invoices`, `purchase_orders`; writes `ticket_log` | `AgentReport` |
| **Accounting** | Watches cash and invoices, checks margins, prepares payments and purchase orders for human approval | `get_today`, `get_cash`, `get_invoice_status`, `list_invoices`, `get_rent_due`, `list_vendors`, `get_pricing`, `check_margin`, `list_approvals`, `list_payments`, `list_purchase_orders`, `request_invoice_payment`, `request_rent_payment`, `request_purchase_order`, `request_price_override`, `add_ticket_note` | reads `desk`, `cash_accounts`, `invoices`, `vendors`, `leases`, `pricing`, `inventory`, `payments`, `approvals`, `purchase_orders`; writes `approvals`, `purchase_orders` (drafts only), `ticket_log`. **Never** writes `payments` or `cash_accounts` | `AgentReport` |
| **Facilities** | Handles the shop space: leases, rent, landlord notices | `get_today`, `get_rent_due`, `get_cash`, `list_approvals`, `add_ticket_note` | reads `desk`, `leases`, `cash_accounts`, `approvals`; writes `ticket_log` | `AgentReport` |
| **Customer Service** | Drafts messages for customers (never sent) | `get_today`, `get_ticket`, `check_stock`, `get_pricing`, `list_drafts`, `draft_customer_message`, `add_ticket_note` | reads `desk`, `tickets`, `ticket_log`, `approvals`, `inventory`, `pricing`, `drafts`; writes `drafts`, `ticket_log` | `AgentReport` |

**Agent loop:** each agent runs PydanticAI's loop: model → tool calls (MCP tools or `delegate`) → tool results → model … until it returns its structured output (`AgentReport` or `BossDecision`). The Boss works the board one ticket at a time because cash is shared across tickets.

**Working-copy tables.** The MCP server adds four tables to `campus_customs_new.db` that the original doesn't have: `approvals` (requests waiting on a human), `purchase_orders`, `drafts` (customer messages) and `ticket_log` (the work log). Resetting the database removes them, and they're rebuilt on first use.

---

## 5. MCP tool catalog (all 27 tools)

Server: `mcp_server/server.py` (FastMCP, stdio). The shop rules are enforced in `mcp_server/shop_db.py`, so they hold no matter who calls. "R" = reads, "W" = writes.

| # | Tool | Added | Tables | Used by |
|---|---|---|---|---|
| 1 | `check_stock(sku, size, needed_qty)` | P3 | R `inventory` | Inventory, Customer Service |
| 2 | `get_invoice_status(invoice_id)` | P3 | R `invoices`, `vendors`, `desk` | Inventory, Accounting |
| 3 | `get_rent_due(lease_id)` | P3 | R `leases`, `desk` | Facilities, Accounting |
| 4 | `get_today()` | P5 | R `desk` | all agents |
| 5 | `list_tickets(status)` | P5 | R `tickets` | Boss, backend |
| 6 | `get_ticket(ticket_id)` | P5 | R `tickets`, `ticket_log`, `approvals`, `drafts` | Boss, Customer Service |
| 7 | `get_pricing(sku)` | P5 | R `pricing` | Inventory, Accounting, Customer Service |
| 8 | `check_margin(sku, qty, unit_price)` | P5 | R `pricing` | Accounting |
| 9 | `list_vendors()` | P5 | R `vendors`, `invoices`, `desk` | Inventory, Accounting |
| 10 | `list_invoices(status, vendor_id)` | P5 | R `invoices`, `vendors`, `desk` | Accounting |
| 11 | `get_cash()` | P5 | R `cash_accounts`, `approvals`, `desk` | Boss, Accounting, Facilities |
| 12 | `list_payments()` | P5 | R `payments` | Boss, Accounting |
| 13 | `list_approvals(status)` | P5 | R `approvals` | Boss, Accounting, Facilities, backend |
| 14 | `list_drafts(ticket_id)` | P5 | R `drafts` | Customer Service |
| 15 | `list_purchase_orders()` | P5 | R `purchase_orders`, `vendors` | Inventory, Accounting |
| 16 | `add_ticket_note(ticket_id, author, note)` | P5 | R `tickets`; W `ticket_log` | all agents |
| 17 | `update_ticket_status(ticket_id, status, resolution)` | P5 | W `tickets.status`, `ticket_log` | Boss |
| 18 | `request_invoice_payment(invoice_id, …)` | P5 | R `invoices`, `vendors`, `desk`, `cash_accounts`; W `approvals` | Accounting |
| 19 | `request_rent_payment(lease_id, …)` | P5 | R `leases`, `cash_accounts`; W `approvals` | Accounting |
| 20 | `request_purchase_order(vendor_id, sku, size, qty, …)` | P5 | R `vendors`, `pricing`, `inventory`, `invoices`, `desk`, `cash_accounts`; W `purchase_orders`, `approvals` | Accounting |
| 21 | `request_price_override(ticket_id, sku, qty, unit_price, …)` | P5 | R `pricing`, `tickets`, `cash_accounts`; W `approvals` | Accounting |
| 22 | `draft_customer_message(ticket_id, recipient, subject, body)` | P5 | R `tickets`; W `drafts` | Customer Service |
| 23 | `human_decide_approval(approval_id, decision, approver)` | P5 | W `approvals`, `purchase_orders`, `ticket_log`; then runs the pay tool | **human only** (dashboard) |
| 24 | `human_pay(approval_id)` — *the pay tool* | P5 | R `approvals`, `desk`, `vendors`; W `cash_accounts`, `payments`, `invoices` / `leases` / `purchase_orders`, `approvals`, `ticket_log` | **human only** |
| 25 | `admin_reset_database()` | P5 | Copies `campus_customs.db` over the working copy | **backend only** (before every full run) |
| 26 | `admin_snapshot()` | P5 | R every table | **backend only** (dashboard view) |
| 27 | `human_add_ticket_note(ticket_id, author, note)` | P9 | R `tickets`; W `ticket_log` (author `Human (name)`) | **human only**: the human's decision on a ticket, which the Boss must follow |

`human_add_ticket_note` was added in Problem 9. Ticket #103 could only be resolved by a human business decision (how much of the order to fill), and until then the human had no way to tell the Boss anything except approve or reject.

`list_payments` was added because, once a human has paid something, Accounting and the Boss need to confirm it from the `payments` table before queuing anything new.

The reference build's `find_restock_vendor` was **not** ported, because it relied on a hand-written SKU-to-vendor list that isn't in the database. Inventory matches the product to a vendor's `specialty` from `list_vendors` instead.

---

## 6. Audit trail — `output/audit_trail.json`

One JSON array that the agents **append to and never wipe**. Each new record replaces only the closing `]`, so earlier runs are kept and the file is valid JSON at every point (`backend/audit.py`). Every record has a `ts` (UTC wall clock), plus `run_id`, `ticket_id`, `agent` and the delegation `chain` where they apply.

| Record `type` | When | Holds |
|---|---|---|
| `db_reset` | Before every full run (and on a dashboard reset) | Reset result |
| `run_started` / `run_finished` | Once per board run | Shop today, ticket ids, model, each ticket's outcome |
| `agent_started` / `agent_finished` | One agent loop | The prompt it got, its allowed tools, its structured output, token usage, or the error |
| `agent_step` `user_prompt` | Each step of the agent loop… | The prompt text |
| `agent_step` `model_response` | … | Model requested and model served, provider response id, text, every tool call with full arguments, finish reason, tokens |
| `agent_step` `model_request` | … | Every tool result (full content) and any retry or error sent back to the model |
| `agent_step` `end` | … | The final structured output |
| `delegation` | Each `delegate` call | From → to, task, reply, status, usage |
| `human_decision` | A human approves or rejects on the dashboard | Approval id, decision, approver, pay-tool result, cash after |
| `human_note` | A human leaves a decision for the Boss | Ticket id, author, note |

Shop facts are never read back from this file. They come only from the MCP server.

**First full run (2026-10-10, run `825329aeee64`):** 235 records: 19 agent loops, 16 delegations, 70 model requests, all served by `gpt-6-luna`. All three tickets ended `awaiting_approval`, with 4 approvals queued (invoice 501 for $840, PO #1 for $8, rent for $2,400, and a hoodie price override at $36.67 with a 40% margin). No payments were made, and cash stayed at $3,400.

---

## 7. Safety: guardrails and token limits

### The eight shop rules and where each one is enforced
| # | Rule (from the Problem 0 brief) | Enforced by |
|---|---|---|
| 1 | `desk.date_today` is "today"; overdue is judged from it | Every date tool computes from `desk.date_today` (`shop_db.today()`); the prompts forbid the real date |
| 2 | Vendor lead times come from `vendors` | `list_vendors` / `request_purchase_order` compute arrival as today + `lead_days`; there's no hard-coded vendor mapping |
| 3 | No new product from a vendor with an open unpaid invoice | `list_vendors.will_ship`; `request_purchase_order` flags it; **the pay tool refuses the PO** |
| 4 | Every payment needs human approval; paying updates the tables | Agents only have `request_*` tools. Only `human_decide_approval` → `human_pay` moves money, and it writes `payments`, `cash_accounts` and the invoice, lease or PO |
| 5 | Not enough cash → the pay tool refuses; no negative balances | `shop_db.pay()` checks `balance − amount ≥ 0` before moving money; agents also plan within `cash_after_pending` |
| 6 | Cash only goes out | There's no revenue tool; price overrides move $0 |
| 7 | Reset to the original before a full run | `run_board(full_run=True)` calls `admin_reset_database` first; the dashboard's "Fresh shift" does the same |
| 8 | Don't email customers or call vendors; drafts stay on the board | There's no outbound tool at all; `draft_customer_message` only writes `drafts` |

### In place now
- **Money needs a named human.** Agents can only *request* payments, purchase orders and discounts. Only `human_decide_approval`/`human_pay` move money, no agent has those tools (the backend refuses to build an agent that lists them), and an agent's name is rejected as the approver.
- **The pay tool enforces the rules in code, not in prompts.** It refuses if the request wasn't approved by a human, if cash would go negative, or if a purchase order's vendor still has an open invoice. A refusal is recorded on the approval and in the ticket log.
- **Least privilege.** Each agent has an allowlist of MCP tools for its role. Only Accounting can request money, only Customer Service writes drafts, and only the Boss changes ticket status.
- **Identity can't be faked.** The backend overwrites `requested_by`/`author` with the calling agent's real name, so an agent can't act as another agent.
- **No outbound contact.** Customer messages are drafts that stay on the board. There's no email, SMS or vendor tool at all.
- **Duplicate requests are blocked.** Asking twice for the same invoice, rent or PO returns the existing approval (in the first run, the invoice was requested 3 times but queued only once).
- **Nothing is invented.** Tools return database values or an error, and "today" is always `desk.date_today`.
- **Safe resets.** The original database is never written. A full run always starts from a fresh copy.
- **The human's word is the human's.** `human_add_ticket_note` is human-only (agents' names are rejected), and the Boss prompt says a `Human (…)` note is the human's decision to follow, within the shop rules.
- **Append-only audit trail** of every model call, tool call, delegation and human decision (§6).

### What a real business would add
- **Split the human tools into their own server.** Today `human_*`/`admin_*` are hidden from the agents by the backend's allowlists, but any MCP client connected to this server (including the vibe coder through `.mcp.json`) can see them. A real shop would serve them from a separate, authenticated service.
- **Real approver identity:** approvers sign in with SSO, and the approver isn't a free-text name. Use role-based approval limits, two approvers above a dollar threshold, and separation of duties (the person who requests can't approve).
- **Spending caps** per day, per vendor and per ticket, enforced in the pay tool, plus a hold for new or changed vendor bank details.
- **Prompt-injection defense:** ticket notes and customer text come from outsiders, so agents treat them as data. Tool permissions, not the model's judgment, decide what can happen.
- **Customer data protection:** keep only the PII a task needs, mask it in logs, and set retention limits on the audit trail.
- **Human review before anything is sent:** even when sending is enabled, drafts go through a person, with tone and claim checks (no unapproved prices or dates).
- **Tamper-evident audit:** write-once storage or hash-chained records, shipped off the machine.
- **Kill switch and monitoring:** `/api/stop` exists now; add alerts for refusals, repeated errors and unusual spending.

### Token limits (multi-agent chats burn tokens fast)
- **One model only:** `gpt-6-luna`, hard-coded and with no override.
- **Per agent loop:** `UsageLimits(request_limit=10)`, i.e. at most 10 model calls per agent run.
- **Delegation limits:** no delegating to yourself or to anyone already up the chain, chains at most 4 agents deep, at most 12 delegations per ticket.
- **One ticket at a time,** and a continue run skips tickets still waiting on a human.
- **Short replies:** prompts ask for ≤120-word reports and few tool calls, and the structured outputs keep handoffs compact.
- **Measured:** the first full run of 3 tickets used about **179k input / 15k output tokens**. Most of it was repeat work (on #101, Inventory and Accounting checked each other's facts). Next steps: a per-ticket token budget (`total_tokens_limit`), telling specialists not to re-delegate work the Boss already assigned, and passing the facts already found along with each delegated task.

---

## 8. Backend routes (Problem 7)

FastAPI in `backend/main.py`. Start it from `backend/` with `uvicorn main:app --reload --port 8000`, which serves `http://localhost:8000`. Every route reads or changes the shop **only through the MCP server**.

- `GET  /api/tickets` returns the three tickets with their status and whether each is `open` or `resolved`.
- `POST /api/tickets/{ticket_id}/run` runs the agent team on one ticket in the background and returns at once (`?wait=true` blocks and returns the Boss's decision). 404 if the ticket doesn't exist, 409 if it's resolved or a run is already going.
- `POST /api/tickets/{ticket_id}/note` (body `{"author": "<human>", "note": "…"}`) leaves the human's decision or instruction on the ticket log for the Boss, through the human-only MCP tool `human_add_ticket_note`.
- `GET  /api/tickets/{ticket_id}/summary` returns what each agent did on the ticket this shift (every run since the last reset) (the Boss's last decision, each specialist's reports, tools used with counts, delegations) plus the customer drafts. It's built from `output/audit_trail.json`, so it survives a backend restart.
- `GET  /api/events?since=N&limit=200&ticket_id=` returns recent agent events: what each agent said, which MCP tools it called with which arguments, the tool results and delegations, plus `next_since` for the next poll (`GET /api/events/stream` is the same feed as live SSE).
- `GET  /api/approvals?status=pending` returns the payments, purchase orders and discounts the agents prepared for a human.
- `POST /api/approvals/{id}/approve` (body `{"approver": "<human name>"}`) is the human approval click. It runs the MCP pay tool, the **only** thing that changes cash, and returns the result and the new checking balance. The pay tool refuses if cash would go negative or the vendor has an open invoice, and agent names are rejected as approvers.
- `POST /api/approvals/{id}/reject` (same body) is the human rejection. No money moves.
- `GET  /api/cash` returns the current checking balance from `cash_accounts`, plus the amount waiting on approval and the cash left after it.
- `POST /api/reset` restores `campus_customs_new.db` from the original `campus_customs.db` for a fresh run.
- CORS allows the Vite desk origin (`http://localhost:5173`, `http://127.0.0.1:5173`) so the browser can call these routes (Problem 8).
- Also available: `POST /api/run` (run the whole board; a full run resets first), `POST /api/stop`, `GET /api/health`, `GET /api/roster`, `GET /api/state` (every table, for the dashboard).

---

## 9. Dashboard (Problem 8)

The React + Vite + TypeScript desk lives in `frontend/`. Start it with `npm run dev` and open http://localhost:5173. It calls the backend at http://localhost:8000. The design rationale is in `output/design.md`.

| Area | Shows | Routes it calls |
|---|---|---|
| **Ticket spike** (left) | The three tickets as paper receipts with their live status (open / team on it / needs you / back to the Boss / blocked / resolved), a RESOLVED rubber stamp, and an x/3-resolved progress bar | `GET /api/tickets`, `GET /api/approvals` |
| **Ticket header** | Subject, requester, notes, the main action (▶ put the team on it / ↻ hand back to the Boss), and a **note-to-the-Boss** box for the human's decision | `POST /api/tickets/{id}/run`, `POST /api/tickets/{id}/note` |
| **Round table** | The five agents in their seats, each showing its live state (thinking / checking the books / waiting on X / done), a speech bubble with its latest words and MCP calls, animated handoff lines between agents, and "not needed" on agents the Boss never called | `GET /api/events?since=N` (polled every ~1s while running, every 2.5s otherwise) |
| **Live wire** | The full transcript: messages, tool-call chips with arguments, handoffs and replies, expandable tool results, human notes | `GET /api/events` |
| **Shift report** | The Boss's call (status, decision, human checklist), one card per specialist (summary, what it created, blockers, tools with counts, delegations), and customer drafts as letters | `GET /api/tickets/{id}/summary` |
| **The till** (right) | The checking balance, which counts down when money leaves; a pending-vs-available bar; a printed receipt for every paid or refused request | `GET /api/cash`, `GET /api/approvals` |
| **Needs your signature** | Approval slips with the amount, reason, the preparing agent, and pay-tool warnings (e.g. "approve the invoice first"). Approve and Reject only work once a human name is entered | `POST /api/approvals/{id}/approve` / `reject` |
| **Top bar** | The shop date (a paper calendar), tokens this shift, the model chip, your name ("on desk"), and ↺ Fresh shift | `GET /api/health`, `POST /api/reset` |

**The human loop:**
1. Start the team on a ticket.
2. When the run ends, the team's requests appear in *Needs your signature*.
3. Approve or reject them; approving a payment pays it through the MCP pay tool, and the till drops.
4. When nothing is left pending, the desk hands the ticket back to the Boss automatically (you can switch this off).
5. The Boss checks `list_payments` and closes the ticket, which gets the RESOLVED stamp.

If a ticket needs a human business decision, the human leaves a note to the Boss and hands it back.

---

## 10. Problem 9: the resolved run

This was a full run on a freshly reset working database, on 2026-10-10, with every agent on `gpt-6-luna`. Details are in `output/desk_tickets.html` (Actual and Cash tabs), `output/resolved_tickets.json`, `output/resolved_board.html` (board screenshots) and `output/audit_trail.json`, where the records start after the `db_reset` at index 362.

| Ticket | Runs | Delegations | Human steps | Cash change | Final |
|---|---|---|---|---|---|
| #101 Bulldog tee | 3 | 8 | approved #1 (invoice 501, $840 → paid), approved #2 (PO 1 × tee S, $8 → paid) | −$848.00 | resolved |
| #102 Rent due | 2 | 2 | approved #3 (rent $2,400 → paid) | −$2,400.00 | resolved |
| #103 Bulk hoodie discount | 3 | 12 | approved #4 (price $36.67, no cash); note: fill the 8 in stock, decline 12 | $0.00 | resolved (was `blocked` after run 2) |

**Cash:** starting balance $3,400.00. $3,400.00 − $840.00 − $8.00 − $2,400.00 = **$152.00**, which matches `cash_accounts.checking` in the working database. No payment was refused and no balance went negative.

**Usage:** 8 runs, 30 agent loops, 110 model calls, about 289k input / 20k output tokens. #103 alone used about half.

**What the run taught us:**
- **#102 matched the plan exactly** (Boss → Facilities → Accounting).
- **On #101 and #103 the Boss fanned out to three specialists at once.** The plan called for one specialist first, so this cost extra delegations and duplicate checks.
- **Accounting held the #101 purchase order until invoice 501 was paid.** That was safer than the plan, which had both queued together.
- **Parallel specialists can race:** Customer Service briefly wrote "no discount pending" on #103 before Accounting's request existed, then corrected it.
- **"Resolved" sometimes needs a human business decision,** not just an approval. That's why `human_add_ticket_note` exists.

