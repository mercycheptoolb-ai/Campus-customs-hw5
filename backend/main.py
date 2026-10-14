"""Campus Customs Multi-Agent Operations — FastAPI backend.

Run from hw5/backend:
  uvicorn main:app --reload --port 8000        (with hw5/.venv active, or ../.venv/bin/uvicorn …)

On startup it launches the MCP server (mcp_server/server.py) as a subprocess on the
working copy data/campus_customs_new.db. Every shop fact and every change goes through
that MCP server — this file never opens the database. The React dashboard (frontend/)
proxies /api here.

Routes for the dashboard:
  GET  /api/tickets                      tickets with open/resolved
  POST /api/tickets/{ticket_id}/run      run the agent team on one ticket
  GET  /api/tickets/{ticket_id}/summary  what each agent did on the ticket this shift (since the last reset)
  POST /api/tickets/{ticket_id}/note     human leaves a decision/instruction for the Boss
  GET  /api/events?since=N               recent agent events (what each agent said, tools used)
  GET  /api/approvals?status=pending     requests the agents prepared for a human
  POST /api/approvals/{id}/approve       human approves → the pay tool moves cash
  POST /api/approvals/{id}/reject        human rejects
  GET  /api/cash                         checking balance from cash_accounts
  POST /api/reset                        restore the original database
"""

from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

import audit
from agents import AGENT_NAMES, shop_mcp
from agents.config import MODEL_NAME
from agents.team import roster, run_board, run_lock, run_one_ticket
from hub import hub
from models import Ticket


@asynccontextmanager
async def lifespan(_app: FastAPI):
    async with shop_mcp.shop_toolset:  # keep one MCP server process for the app's lifetime
        yield


app = FastAPI(title="Campus Customs Multi-Agent Operations", version="1.1.0", lifespan=lifespan)
# The React desk (Vite dev server) runs on :5173 and calls this API directly from the browser.
VITE_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
app.add_middleware(CORSMiddleware, allow_origins=VITE_ORIGINS, allow_methods=["*"], allow_headers=["*"])

_run_task: asyncio.Task | None = None


class RunRequest(BaseModel):
    full_run: bool = True  # full run = reset DB to the original, then work every open ticket
    ticket_ids: list[int] | None = None


class HumanNote(BaseModel):
    author: str = Field(min_length=1, max_length=60, description="The human writing the note — never an agent name.")
    note: str = Field(min_length=1, max_length=1000)


class HumanApproval(BaseModel):
    approver: str = Field(min_length=1, max_length=60, description="The human clicking the button — never an agent name.")


def _running() -> bool:
    return _run_task is not None and not _run_task.done()


async def _mcp(tool: str, **args: Any) -> Any:
    """Call an MCP tool; a broken shop rule comes back as HTTP 400 with the tool's message."""
    try:
        return await shop_mcp.call(tool, **args)
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


def _start(coro) -> None:
    """Run agent work in the background (one run at a time) so the request returns immediately."""
    global _run_task
    if _running() or run_lock.locked():
        raise HTTPException(409, "A run is already in progress.")

    async def work():
        async with run_lock:
            try:
                await coro
            except Exception as exc:
                hub.emit("run_error", error=str(exc)[:500])

    _run_task = asyncio.create_task(work())


# ---------------------------------------------------------------- tickets + running the team


@app.get("/api/tickets")
async def list_tickets():
    """The tickets on the board and whether each is open or resolved."""
    tickets = await _mcp("list_tickets")
    return {
        "tickets": [
            {
                "id": t["id"],
                "type": t["type"],
                "requester": t["requester"],
                "subject": t["subject"],
                "status": t["status"],  # open | in_progress | awaiting_approval | blocked | resolved
                "resolved": t["status"] == "resolved",
                "state": "resolved" if t["status"] == "resolved" else "open",
                "sku": t["sku"],
                "size": t["size"],
                "qty": t["qty"],
                "lease_id": t["lease_id"],
                "invoice_id": t["invoice_id"],
                "notes": t["notes"],
            }
            for t in tickets
        ]
    }


@app.post("/api/tickets/{ticket_id}/run", status_code=202)
async def run_ticket_route(ticket_id: int, wait: bool = Query(False, description="Block until the team finishes and return the outcome.")):
    """Run the agent team on one ticket. Returns at once; follow progress with GET /api/events."""
    tickets = {t["id"]: t for t in await _mcp("list_tickets")}
    if ticket_id not in tickets:
        raise HTTPException(404, f"Ticket {ticket_id} not found.")
    if tickets[ticket_id]["status"] == "resolved":
        raise HTTPException(409, f"Ticket {ticket_id} is already resolved.")
    ticket = Ticket(**tickets[ticket_id])
    since = len(hub.events)
    if wait:
        if _running() or run_lock.locked():
            raise HTTPException(409, "A run is already in progress.")
        async with run_lock:
            outcome = await run_one_ticket(hub.emit, ticket)
        return {"started": True, "finished": True, "ticket_id": ticket_id, "outcome": outcome.model_dump()}
    _start(run_one_ticket(hub.emit, ticket))
    return {"started": True, "ticket_id": ticket_id, "events": f"/api/events?since={since}"}


@app.get("/api/tickets/{ticket_id}/summary")
async def ticket_summary(ticket_id: int):
    """What each agent did on the ticket this shift (every run since the last database reset) — built from
    output/audit_trail.json, so it survives a backend restart. Drafts come from the MCP server."""
    trail = audit.read_all()
    last_reset = max((i for i, r in enumerate(trail) if r.get("type") == "db_reset"), default=-1)
    records = [r for r in trail[last_reset + 1 :] if r.get("ticket_id") == ticket_id and r.get("run_id")]
    drafts = await _mcp("list_drafts", ticket_id=ticket_id)
    if not records:
        return {"ticket_id": ticket_id, "run_id": None, "runs": [], "agents": [], "boss": None, "drafts": drafts}
    runs = list(dict.fromkeys(r["run_id"] for r in records))
    agents: dict[str, dict] = {}
    boss = None

    def card(name: str) -> dict:
        return agents.setdefault(name, {"agent": name, "runs": 0, "tools": {}, "asked_by": [], "delegated_to": [], "reports": []})

    for r in records:
        if r["type"] == "delegation":
            card(r["from_agent"])["delegated_to"].append(r["to_agent"])
            continue
        if not r.get("agent"):
            continue
        a = card(r["agent"])
        if r["type"] == "agent_started":
            a["runs"] += 1
            if len(r.get("chain", [])) > 1:
                a["asked_by"].append(r["chain"][-2])
        elif r["type"] == "agent_step" and r.get("kind") == "model_response":
            for c in r.get("tool_calls", []):
                if c["tool"] not in ("final_result", "delegate"):
                    a["tools"][c["tool"]] = a["tools"].get(c["tool"], 0) + 1
        elif r["type"] == "agent_finished" and r.get("status") == "done":
            out = r.get("output") or {}
            if r.get("agent") == "Boss":
                boss = out
            else:
                a["reports"].append(out)
    last = runs[-1]
    finished = any(r["type"] == "agent_finished" and r.get("agent") == "Boss" and len(r.get("chain", [])) == 1 for r in records if r["run_id"] == last)
    order = ["Boss", "Inventory", "Accounting", "Facilities", "Customer Service"]
    return {
        "ticket_id": ticket_id,
        "run_id": last,
        "runs": runs,
        "finished": finished,
        "boss": boss,
        "agents": sorted(agents.values(), key=lambda a: order.index(a["agent"]) if a["agent"] in order else 99),
        "drafts": drafts,
    }


@app.post("/api/tickets/{ticket_id}/note")
async def human_note(ticket_id: int, body: HumanNote):
    """The human's decision or instruction on a ticket (e.g. how to close it). The Boss reads it on the next run."""
    if body.author.strip() in AGENT_NAMES:
        raise HTTPException(400, "Notes here come from a human, not an agent.")
    result = await _mcp("human_add_ticket_note", ticket_id=ticket_id, author=body.author.strip(), note=body.note.strip())
    hub.emit("human_note", ticket_id=ticket_id, author=body.author.strip(), note=body.note.strip())
    audit.append("human_note", ticket_id=ticket_id, author=body.author.strip(), note=body.note.strip())
    return result


@app.post("/api/run")
async def start_run(body: RunRequest):
    """Run the whole board. A full run resets the database to the original values first."""
    if body.full_run:
        hub.clear()
    _start(run_board(hub.emit, full_run=body.full_run, ticket_ids=body.ticket_ids))
    return {"started": True, "full_run": body.full_run, "run_id": hub.run_id}


@app.post("/api/stop")
async def stop_run():
    if _running():
        _run_task.cancel()
        hub.emit("run_error", error="Run stopped by the human operator.")
    return {"stopped": True}


# ---------------------------------------------------------------- agent events


def _event_view(e: dict) -> dict:
    """One dashboard event, flattened to: who, what they said, which tools they used."""
    view = {k: e.get(k) for k in ("seq", "run_id", "ts", "type", "ticket_id") if e.get(k) is not None}
    kind = e.get("kind")
    if e["type"] == "agent_step" and kind == "model_response":
        calls = e.get("tool_calls", [])
        final = next((c["args"] for c in calls if c["tool"] == "final_result"), None)
        said = e.get("text") or ""
        if final and not said:  # the agent's structured answer (AgentReport / BossDecision) is what it "said"
            said = final.get("summary") or final.get("decision") or json.dumps(final)
        view.update(
            type="agent_said",
            agent=e["agent"],
            said=said,
            final=final is not None,
            tools=[{"tool": c["tool"], "args": c["args"]} for c in calls if c["tool"] != "final_result"],
            model=e.get("provider_reported_model") or e.get("model"),
            tokens={"in": e.get("usage", {}).get("input_tokens", 0), "out": e.get("usage", {}).get("output_tokens", 0)},
        )
    elif e["type"] == "agent_step" and kind == "tool_results":
        view.update(
            type="tool_results",
            agent=e["agent"],
            results=[{"tool": r["tool"], "content": r["content"]} for r in e.get("tool_returns", [])],
            retries=e.get("retries", []),
        )
    elif e["type"] in ("delegation_started", "delegation_done"):
        view.update(
            delegation_id=e.get("id"),
            agent=e.get("from_agent"),
            to_agent=e.get("to_agent"),
            said=e.get("task") or e.get("reply") or "",
            status=e.get("status"),
        )
    elif e["type"] in ("agent_started", "agent_done"):
        view.update(agent=e.get("agent"), said=e.get("reply") or "", chain=e.get("chain"))
    else:  # ticket_started/done, run_started/done, approval_decided, db_reset, run_error
        view.update({k: v for k, v in e.items() if k not in view and k not in ("t_ms", "usage_totals")})
    return view


@app.get("/api/events")
async def recent_events(
    since: int = Query(0, ge=0, description="Return events with seq >= since (use next_since from the last call)."),
    limit: int = Query(200, ge=1, le=1000),
    ticket_id: int | None = None,
):
    """Recent agent events — what each agent said and which tools they used — for the board to poll."""
    events = [e for e in hub.events[since:] if ticket_id is None or e.get("ticket_id") == ticket_id]
    return {
        "run_id": hub.run_id,
        "running": _running(),
        "next_since": len(hub.events),
        "usage": hub.totals(),
        "events": [_event_view(e) for e in events[-limit:]],
    }


@app.get("/api/events/stream")
async def stream_events(since: int = 0):
    """The same events as a live Server-Sent Events stream."""

    async def gen():
        async for event in hub.stream(since):
            yield f"data: {json.dumps(event, default=str)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---------------------------------------------------------------- human approval + money


@app.get("/api/approvals")
async def list_approvals(status: str | None = Query(None, description="pending | approved | rejected | paid | refused")):
    """Payments, purchase orders and discounts the agents prepared, waiting on (or decided by) a human."""
    return {"approvals": await _mcp("list_approvals", status=status)}


async def _decide(approval_id: int, decision: str, approver: str) -> dict:
    approver = approver.strip()
    if approver in AGENT_NAMES:
        raise HTTPException(400, "Approver must be a human, not an agent.")
    result = await _mcp("human_decide_approval", approval_id=approval_id, decision=decision, approver=approver)
    cash = await _mcp("get_cash")
    hub.emit("approval_decided", approval_id=approval_id, decision=decision, approver=approver, result=result)
    audit.append("human_decision", approval_id=approval_id, decision=decision, approver=approver, result=result, cash_after=cash["total_cash"])
    return {**result, "checking_balance": _checking(cash)["balance"]}


@app.post("/api/approvals/{approval_id}/approve")
async def approve(approval_id: int, body: HumanApproval):
    """A human approves a request. For a payment or purchase order this runs the MCP pay tool — the only
    thing that changes cash. The pay tool refuses (status 'refused') if cash would go negative or the
    vendor still has an open invoice."""
    return await _decide(approval_id, "approve", body.approver)


@app.post("/api/approvals/{approval_id}/reject")
async def reject(approval_id: int, body: HumanApproval):
    return await _decide(approval_id, "reject", body.approver)


def _checking(cash: dict) -> dict:
    return next((a for a in cash["accounts"] if a["name"] == "checking"), {"name": "checking", "balance": None, "date": None})


@app.get("/api/cash")
async def cash():
    """Current checking balance from cash_accounts, plus what is waiting on human approval."""
    c = await _mcp("get_cash")
    checking = _checking(c)
    return {
        "account": "checking",
        "balance": checking["balance"],
        "as_of": checking["date"],
        "shop_today": c["today"],
        "pending_approval_amount": c["pending_approval_amount"],
        "cash_after_pending": c["cash_after_pending"],
    }


# ---------------------------------------------------------------- reset + misc


@app.post("/api/reset")
async def reset():
    """Restore data/campus_customs_new.db from the original campus_customs.db for a fresh run."""
    if _running():
        raise HTTPException(409, "A run is in progress.")
    result = await _mcp("admin_reset_database")
    audit.append("db_reset", run_id=None, result=result, by="dashboard")
    hub.clear()
    hub.emit("db_reset", note="Working copy restored from campus_customs.db.")
    return result


@app.get("/api/health")
async def health():
    tools = [t.name for t in await shop_mcp.shop_toolset.list_tools()]
    return {
        "ok": True,
        "model": MODEL_NAME,
        "working_db": shop_mcp.WORKING_DB.name,
        "mcp_tools": len(tools),
        "portkey_key_set": bool(os.getenv("PORTKEY_API_KEY", "").strip()),
        "running": _running(),
    }


@app.get("/api/roster")
def get_roster():
    return {"model": MODEL_NAME, "agents": roster()}


@app.get("/api/state")
async def state():
    snap = await _mcp("admin_snapshot")
    return {**snap, "running": _running(), "usage": hub.totals(), "run_id": hub.run_id}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
