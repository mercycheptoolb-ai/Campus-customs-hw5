"""Turn every PydanticAI agent-loop node into a dashboard event and an audit record.

run_traced() drives agent.iter() node by node. For each node it:
  * emits an `agent_step` to the dashboard (clipped, for display), and
  * appends a full `agent_step` record to output/audit_trail.json (see audit.py):
    user prompt → model response (text, tool calls + args, model served, tokens)
    → tool results (full content, retries) → … → end (final structured output).
"""

from __future__ import annotations

import time
from typing import Any, Callable

from pydantic_ai import Agent
from pydantic_ai.messages import RetryPromptPart, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.usage import UsageLimits

import audit
from agents.config import MODEL_NAME, build_model

Emit = Callable[..., None]
LIMITS = UsageLimits(request_limit=10)  # per agent run — multi-agent chats burn tokens fast


def clip(value: Any, limit: int = 700) -> str:
    text = value if isinstance(value, str) else str(value)
    return text if len(text) <= limit else text[:limit] + f"… (+{len(text) - limit} chars)"


def usage_dict(usage: Any) -> dict:
    return {
        "requests": getattr(usage, "requests", 0),
        "input_tokens": getattr(usage, "input_tokens", 0) or 0,
        "output_tokens": getattr(usage, "output_tokens", 0) or 0,
        "cache_read_tokens": getattr(usage, "cache_read_tokens", 0) or 0,
        "tool_calls": getattr(usage, "tool_calls", 0) or 0,
    }


def describe_node(node: Any) -> tuple[str, dict] | None:
    if Agent.is_model_request_node(node):
        parts = node.request.parts
        returns = [
            {"tool": p.tool_name, "tool_call_id": p.tool_call_id, "content": clip(p.model_response_str(), 500)}
            for p in parts
            if isinstance(p, ToolReturnPart)
        ]
        retries = [clip(p.model_response(), 300) for p in parts if isinstance(p, RetryPromptPart)]
        if not returns and not retries:
            return None
        return "tool_results", {"tool_returns": returns, "retries": retries}

    if Agent.is_call_tools_node(node):
        resp = node.model_response
        text = "".join(p.content for p in resp.parts if isinstance(p, TextPart))
        calls = [
            {"tool": p.tool_name, "tool_call_id": p.tool_call_id, "args": p.args_as_dict()}
            for p in resp.parts
            if isinstance(p, ToolCallPart)
        ]
        return "model_response", {
            "model": MODEL_NAME,
            "provider_reported_model": resp.model_name,
            "text": clip(text),
            "tool_calls": calls,
            "usage": usage_dict(resp.usage),
        }

    return None


def audit_context(deps: Any, agent_name: str) -> dict:
    """Who/where for every audit record: run, ticket, agent, and the delegation chain."""
    ticket = getattr(deps, "ticket", None)
    return {
        "run_id": getattr(ticket, "run_id", None),
        "ticket_id": getattr(ticket, "ticket_id", None),
        "agent": agent_name,
        "chain": list(getattr(deps, "chain", ()) or ()),
    }


def audit_node(node: Any) -> dict | None:
    """Full (unclipped up to audit.MAX_FIELD_CHARS) record of one agent-loop node."""
    if Agent.is_user_prompt_node(node):
        return {"kind": "user_prompt", "prompt": node.user_prompt if isinstance(node.user_prompt, str) else str(node.user_prompt)}
    if Agent.is_model_request_node(node):
        parts = node.request.parts
        returns = [
            {"tool": p.tool_name, "tool_call_id": p.tool_call_id, "content": p.model_response_str()}
            for p in parts
            if isinstance(p, ToolReturnPart)
        ]
        retries = [{"tool": p.tool_name, "tool_call_id": p.tool_call_id, "error": p.model_response()} for p in parts if isinstance(p, RetryPromptPart)]
        return {"kind": "model_request", "tool_returns": returns, "retries": retries}
    if Agent.is_call_tools_node(node):
        resp = node.model_response
        return {
            "kind": "model_response",
            "model_requested": MODEL_NAME,
            "model_served": resp.model_name,
            "provider_response_id": resp.provider_response_id,
            "text": "".join(p.content for p in resp.parts if isinstance(p, TextPart)),
            "tool_calls": [
                {"tool": p.tool_name, "tool_call_id": p.tool_call_id, "args": p.args_as_dict()}
                for p in resp.parts
                if isinstance(p, ToolCallPart)
            ],
            "finish_reason": resp.finish_reason,
            "usage": usage_dict(resp.usage),
        }
    if Agent.is_end_node(node):
        out = node.data.output
        return {"kind": "end", "output": out.model_dump() if hasattr(out, "model_dump") else str(out)}
    return None


async def run_traced(agent: Agent, prompt: str, *, emit: Emit, agent_name: str, deps: Any, **extra: Any) -> tuple[Any, dict]:
    """Run one agent loop to completion (agent.iter), emitting each step. Returns (output, usage)."""
    started = time.perf_counter()
    async with agent.iter(prompt, deps=deps, model=build_model(), usage_limits=LIMITS) as run:
        step = audit_step = 0
        ctx = audit_context(deps, agent_name)
        async for node in run:
            if (record := audit_node(node)) is not None:
                audit_step += 1
                audit.append("agent_step", **ctx, step=audit_step, **record)
            described = describe_node(node)
            if described is None:
                continue
            step += 1
            kind, data = described
            emit("agent_step", agent=agent_name, step=step, kind=kind, **extra, **data)
        usage = usage_dict(run.usage() if callable(run.usage) else run.usage)
        usage["seconds"] = round(time.perf_counter() - started, 2)
        return run.result.output, usage
