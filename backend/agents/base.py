"""Shared machinery for the five agents: prompt loading, agent factory, delegation, and the agent loop.

Each agent file (boss.py, inventory.py, ...) declares an AgentSpec and calls make_agent().
Every agent gets:
  * its own prompt file from backend/prompts/ plus the shared shop rules
  * a role-filtered view of the campus-customs MCP toolset
  * the `delegate` tool, so ANY agent can hand work to ANY other agent (full connectivity)
  * a structured output type (AgentReport, or BossDecision for the Boss)

Guard rails keep delegation from looping or burning tokens:
  * an agent cannot delegate to itself or to anyone already up its delegation chain
  * chains are at most MAX_DEPTH agents deep (Boss → A → B → C)
  * at most MAX_DELEGATIONS_PER_TICKET delegations per ticket
  * every agent run is capped at 10 model requests (events.LIMITS)
"""

from __future__ import annotations

from pathlib import Path

from pydantic_ai import Agent, RunContext

import audit
from agents import shop_mcp
from agents.events import clip, run_traced
from models import AgentName, AgentOutput, AgentSpec, DelegationResult, TeamDeps

PROMPTS = Path(__file__).resolve().parents[1] / "prompts"
MAX_DEPTH = 4
MAX_DELEGATIONS_PER_TICKET = 12

# Tools only the dashboard's human operator may call. No agent spec may list them.
HUMAN_ONLY_TOOLS = frozenset({"human_decide_approval", "human_pay", "human_add_ticket_note", "admin_reset_database", "admin_snapshot"})

SPECS: dict[str, AgentSpec] = {}
AGENTS: dict[str, Agent[TeamDeps, AgentOutput]] = {}


def prompt_for(spec: AgentSpec) -> str:
    own = (PROMPTS / spec.prompt_file).read_text(encoding="utf-8")
    shared = (PROMPTS / "shared_rules.md").read_text(encoding="utf-8")
    teammates = "\n".join(f"- {s.name}: {s.role}" for s in SPECS.values() if s.name != spec.name)
    return f"You are the {spec.name} agent at Campus Customs.\n\n{own}\n\n## Teammates you can delegate to\n{teammates}\n\n{shared}"


def output_text(output: AgentOutput | str) -> str:
    return output.as_text() if hasattr(output, "as_text") else str(output)


async def delegate(ctx: RunContext[TeamDeps], to_agent: AgentName, task: str) -> DelegationResult:
    """Hand a task to another agent on the team and get their report back.

    Args:
        to_agent: Boss, Inventory, Accounting, Facilities, or Customer Service.
        task: What you need from them, with the ticket id and the concrete facts they need
            (SKU, size, qty, vendor id, invoice id, lease id, amounts, dates).
    """
    d = ctx.deps
    t = d.ticket
    if to_agent not in AGENTS:
        return DelegationResult(agent=to_agent, status="error", reply=f"Unknown agent. Choose one of {list(AGENTS)}.")
    if to_agent == d.agent:
        return DelegationResult(agent=to_agent, status="error", reply="You cannot delegate to yourself — do it with your own tools.")
    if to_agent in d.chain:
        return DelegationResult(
            agent=to_agent, status="error", reply=f"{to_agent} already asked for this work up the chain ({' → '.join(d.chain)}). Answer them instead."
        )
    if len(d.chain) >= MAX_DEPTH:
        return DelegationResult(agent=to_agent, status="error", reply="Delegation chain is too deep. Finish with what you have.")
    if t.delegations >= MAX_DELEGATIONS_PER_TICKET:
        return DelegationResult(agent=to_agent, status="error", reply="Delegation limit for this ticket reached. Finish with what you have.")

    t.delegations += 1
    t.next_id += 1
    did = t.next_id
    chain = (*d.chain, to_agent)
    t.emit("delegation_started", id=did, ticket_id=t.ticket_id, from_agent=d.agent, to_agent=to_agent, task=clip(task, 600), chain=list(chain))
    prompt = f"Ticket #{t.ticket_id}. {d.agent} asks you:\n{task}\n\n(Delegation chain so far: {' → '.join(chain)}.)"
    try:
        report, usage = await run_agent(to_agent, prompt, TeamDeps(agent=to_agent, chain=chain, ticket=t))
        result = DelegationResult(agent=to_agent, status="done", report=report, reply=output_text(report))
    except Exception as exc:  # report back to the caller instead of killing the ticket
        usage = None
        result = DelegationResult(agent=to_agent, status="error", reply=f"{to_agent} hit an error: {clip(exc, 300)}")
    audit.append(
        "delegation",
        run_id=t.run_id,
        ticket_id=t.ticket_id,
        delegation_id=did,
        from_agent=d.agent,
        to_agent=to_agent,
        chain=list(chain),
        task=task,
        status=result.status,
        reply=result.reply,
        usage=usage,
    )
    t.emit(
        "delegation_done",
        id=did,
        ticket_id=t.ticket_id,
        from_agent=to_agent,
        to_agent=d.agent,
        reply=clip(result.reply, 1500),
        status=result.status,
        usage=usage,
    )
    return result


def make_agent(spec: AgentSpec) -> Agent[TeamDeps, AgentOutput]:
    """Build one PydanticAI agent from its spec and register it with the team."""
    allowed = frozenset(spec.tools)
    if forbidden := allowed & HUMAN_ONLY_TOOLS:
        raise ValueError(f"{spec.name} must not get human-only tools: {sorted(forbidden)}")
    SPECS[spec.name] = spec
    agent = Agent(
        deps_type=TeamDeps,
        output_type=spec.output_type,
        name=spec.name,
        instructions=lambda: prompt_for(spec),  # built at run time so every teammate is listed
        toolsets=[shop_mcp.shop_toolset.filtered(lambda _ctx, td: td.name in allowed)],
        tools=[delegate],
    )
    AGENTS[spec.name] = agent
    return agent


async def run_agent(name: str, prompt: str, deps: TeamDeps) -> tuple[AgentOutput, dict]:
    """One agent loop: model → tool calls (MCP tools / delegate) → model … until it returns its output type."""
    t = deps.ticket
    ctx = {"run_id": t.run_id, "ticket_id": t.ticket_id, "agent": name, "chain": list(deps.chain)}
    t.emit("agent_started", agent=name, ticket_id=t.ticket_id, chain=list(deps.chain))
    audit.append("agent_started", **ctx, tools=[*SPECS[name].tools, "delegate"], prompt=prompt)
    try:
        output, usage = await run_traced(AGENTS[name], prompt, emit=t.emit, agent_name=name, deps=deps, ticket_id=t.ticket_id)
    except Exception as exc:
        audit.append("agent_finished", **ctx, status="error", error=f"{type(exc).__name__}: {exc}")
        raise
    audit.append("agent_finished", **ctx, status="done", output=output.model_dump() if hasattr(output, "model_dump") else str(output), usage=usage)
    t.emit("agent_done", agent=name, ticket_id=t.ticket_id, reply=clip(output_text(output), 1500), usage=usage)
    return output, usage
