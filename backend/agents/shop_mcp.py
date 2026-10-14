"""The one connection from the backend to the Campus Customs MCP server.

The backend starts mcp_server/server.py as a stdio subprocess when FastAPI starts and keeps
it open. Agents get filtered views of this toolset (see base.py and each agent file); the dashboard's human
actions (approve/reject, reset, snapshot) go through call() on the same connection.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from fastmcp import Client
from fastmcp.client.transports import PythonStdioTransport
from pydantic_ai import RunContext
from pydantic_ai.mcp import MCPToolset

HW5_ROOT = Path(__file__).resolve().parents[2]
SERVER_SCRIPT = HW5_ROOT / "mcp_server" / "server.py"
WORKING_DB = HW5_ROOT / "data" / "campus_customs_new.db"

# Tool arg that names the acting agent. The backend fills it in from the caller so an
# agent cannot act under another agent's name.
IDENTITY_ARG = {
    "add_ticket_note": "author",
    "draft_customer_message": "author",
    "request_invoice_payment": "requested_by",
    "request_rent_payment": "requested_by",
    "request_purchase_order": "requested_by",
    "request_price_override": "requested_by",
}


async def _stamp_identity(ctx: RunContext[Any], call_tool, name: str, args: dict[str, Any]):
    agent = getattr(ctx.deps, "agent", None)
    if agent and name in IDENTITY_ARG:
        args = {**args, IDENTITY_ARG[name]: agent}
    return await call_tool(name, args)


def _transport() -> PythonStdioTransport:
    return PythonStdioTransport(
        SERVER_SCRIPT,
        python_cmd=sys.executable,
        env={"SHOP_DB": str(WORKING_DB), "PYDANTIC_AI_NO_BANNER": "1"},
        cwd=str(HW5_ROOT),
    )


shop_toolset = MCPToolset(
    Client(_transport()),
    id="campus-customs",
    process_tool_call=_stamp_identity,
    tool_error_behavior="failed",  # a broken shop rule goes back to the model so it can adapt
)


def _decode(result: Any) -> Any:
    if isinstance(result, str):
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return result
    return result


async def call(name: str, **args: Any) -> Any:
    """Call an MCP tool directly (human/admin actions from the dashboard)."""
    return _decode(await shop_toolset.direct_call_tool(name, args))
