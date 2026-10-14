# Campus Customs Multi-Agent Operations (HW5)

A five-agent team runs a small campus merch shop: the Boss, Inventory, Accounting, Facilities and Customer Service. The agents work tickets off a board. A human watches them on a React dashboard and approves any money that moves.

```
React desk (frontend/, :5173)  ──HTTP──▶  FastAPI backend (backend/, :8000)  ──MCP stdio──▶  MCP server (mcp_server/)
 pick tickets, watch agents,               5 PydanticAI agents on gpt-6-luna          27 shop tools over
 approve payments, see the till            (via Portkey), audit trail                 data/campus_customs_new.db
```

Every shop fact and every change goes through the MCP server. The backend never opens the database itself.

---

## Layout

```
hw5/
├── AI_prompts.md              every prompt I typed, per problem
├── requirements.txt           Python deps (MCP server + backend)
├── .env.example               copy to .env and add your PORTKEY_API_KEY
├── .gitignore                 keeps .env, .venv, node_modules out of git
├── .mcp.json                  registers the MCP server with Claude Code (vibe coder)
├── README.md
├── data/
│   ├── campus_customs.db      ORIGINAL database — never written to
│   └── campus_customs_new.db  WORKING copy — what the app reads and writes
├── mcp_server/                FastMCP server (server.py) + shop rules (shop_db.py)
├── backend/
│   ├── main.py                FastAPI routes
│   ├── models.py              data types (Ticket, AgentSpec, AgentReport, BossDecision, …)
│   ├── agents/                one file per agent + delegation, agent loop, MCP client
│   ├── prompts/               boss.md, inventory.md, accounting.md, facilities.md,
│   │                          customer_service.md (+ shared_rules.md: the 8 shop rules)
│   ├── audit.py, hub.py       append-only audit trail, live event feed
│   └── requirements.txt       → ../requirements.txt
├── frontend/                  React + Vite + TypeScript desk
└── output/
    ├── harness.md             tables, MCP tools, agents, routes, dashboard, safety
    ├── mcp_smoke.json         Problem 4 tool tests
    ├── desk_tickets.html      plan vs. actual per ticket, Cash ledger, Reflection
    ├── design.md              dashboard design choices
    ├── resolved_tickets.json  outcome, agent contributions, human approvals
    ├── resolved_board.html    screenshots of the resolved board
    ├── audit_trail.json       every agent-loop step of every run (append-only)
    └── github_url.txt
```

---

## 1. One-time setup

You need Python 3.11+ (built on 3.13) and Node 20+ (built on 24).

```bash
cd hw5
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
npm --prefix frontend install
cp .env.example .env          # then edit .env and set PORTKEY_API_KEY=<your key>
```

Every agent uses **only `gpt-6-luna` through Portkey**. The model name is a fixed constant in `backend/agents/config.py`. The key is read from `PORTKEY_API_KEY` in `.env` (in `hw5/` or any parent folder), and it is never logged or committed. Portkey's responses report the served model as **`gpt-6-luna-global`**, which is its deployment name for `gpt-6-luna`, not a different model. The code only ever requests `gpt-6-luna`, and the audit trail records both (`model_requested` / `model_served`).

---

## 2. Copy the original database to the working copy (clean run)

`data/campus_customs.db` is the untouched original. The app only reads and writes `data/campus_customs_new.db`.

> **Note:** the committed working copy is in its **final state after my Problem 9 run**: all three tickets resolved, $152.00 left in checking, three payments recorded. Copy the original over it whenever you want a clean start.

```bash
cp data/campus_customs.db data/campus_customs_new.db
```

The MCP server adds four working-copy-only tables (`approvals`, `purchase_orders`, `drafts`, `ticket_log`) the first time it runs.

---

## 3. Start the MCP server

**You don't need to start it by hand to run the app.** The FastAPI backend launches `mcp_server/server.py` as a stdio subprocess when it starts, and keeps it running.

To run it on its own (for example to test the tools):

```bash
.venv/bin/python mcp_server/server.py          # stdio MCP server; Ctrl+C to stop
```

To use it from **Claude Code**, open Claude Code in `hw5/`. `.mcp.json` registers it as `campus-customs`, so tools like `check_stock`, `get_invoice_status` and `get_rent_due` are callable right away. The full list of 27 tools is in `mcp_server/README.md`.

---

## 4. Start the FastAPI backend

```bash
cd backend
../.venv/bin/uvicorn main:app --reload --port 8000      # → http://localhost:8000
```

Check it's up: `curl http://localhost:8000/api/health` should show `"model": "gpt-6-luna"`, `"mcp_tools": 27`, `"portkey_key_set": true`.

The main routes (full list in `output/harness.md` §8):

| Route | What it does |
|---|---|
| `GET /api/tickets` | The three tickets, open or resolved |
| `POST /api/tickets/{id}/run` | Run the agent team on one ticket |
| `GET /api/events?since=N` | What each agent said and which tools it used |
| `GET /api/tickets/{id}/summary` | What each agent did on the ticket |
| `GET /api/approvals` | Requests waiting for a human |
| `POST /api/approvals/{id}/approve` | **The only route that moves cash** (body `{"approver": "<your name>"}`) |
| `POST /api/approvals/{id}/reject` | Reject a request |
| `POST /api/tickets/{id}/note` | Leave a human decision for the Boss |
| `GET /api/cash` | The checking balance from `cash_accounts` |
| `POST /api/reset` | Restore the original database |
| `POST /api/run` | Run the whole board (`{"full_run": true}` resets first) |

---

## 5. Start the React board

In a second terminal (leave the backend running):

```bash
cd frontend
npm run dev                                              # → http://localhost:5173 (opens in your browser)
```

The desk calls the backend at `http://localhost:8000`; the backend's CORS allows `http://localhost:5173`. To point it somewhere else, set `VITE_API_BASE`.

---

## 6. Reset the database before a full three-ticket run

Always start a full run from the original values. Any of these works:

- On the desk, click **↺ Fresh shift** (top right), which calls `POST /api/reset`.
- `curl -X POST http://localhost:8000/api/reset`
- With the backend stopped: `cp data/campus_customs.db data/campus_customs_new.db`

`POST /api/run` with `{"full_run": true}` also resets automatically before it works every open ticket.

### Resolving the three tickets on the desk

1. Type your name in **on desk**. Approve only works with a human name.
2. Pick **#101**, then press **▶ Put the team on it**. Watch the round table and the live wire.
3. When the run ends, sign the requests under **Needs your signature**. Approve **invoice 501 before any purchase order**, or the pay tool refuses the PO. The till drops on every payment.
4. With *"hand back to the Boss after I sign"* on, the Boss picks the ticket back up and closes it. It gets the **RESOLVED** stamp.
5. Do the same for **#102** and **#103**. If a ticket comes back **blocked** (#103: 20 hoodies wanted, 8 in stock, not enough cash to restock), leave your decision in **note to the Boss** and hand it back.

Expected money for a clean run: **$3,400.00 → −$840 (invoice 501) → −$8 (tee PO) → −$2,400 (rent) = $152.00**. See the Cash tab in `output/desk_tickets.html`.

---

## Shop rules (enforced in `mcp_server/shop_db.py`, not just in prompts)

1. "Today" is `desk.date_today` (2026-08-31), never the wall clock.
2. Vendor lead times come from `vendors.lead_days`.
3. A vendor with an open unpaid invoice won't ship; the pay tool refuses its POs.
4. Every payment needs a named human's approval; paying updates `payments`, `cash_accounts` and the invoice, lease or PO.
5. Not enough cash → the pay tool refuses. No negative balances.
6. Cash only goes out (no revenue is modelled).
7. Reset to the original before a full run.
8. No emails or vendor calls: customer messages are drafts that stay on the board.

More detail: `output/harness.md` (tables, tools, agents, routes, dashboard, safety), `output/design.md` (dashboard), `mcp_server/README.md` (tools).
