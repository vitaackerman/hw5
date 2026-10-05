"""The Campus Customs agent team: a boss plus four specialists, all PydanticAI agents.

Every agent gets the same `delegate` tool, so any agent can hand work to any
other (full connectivity). Cycles, self-delegation, depth and total
delegations are capped. Shop facts and changes come only from the MCP server;
each agent sees just the MCP tools its role needs.
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic_ai import Agent, RunContext
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.messages import RetryPromptPart, TextPart, ToolCallPart, ToolReturnPart, UserPromptPart
from pydantic_ai.usage import RunUsage

from backend.audit import AuditTrail, short
from backend.config import (
    AGENT_RETRIES,
    AUDIT_PATH,
    HUMAN_ONLY_TOOLS,
    MAX_DELEGATION_DEPTH,
    MAX_DELEGATIONS,
    MODEL_SETTINGS,
    PROMPTS_DIR,
    TEAM_LIMITS,
    get_model,
    mcp_toolset,
)
from backend.models import (
    AGENT_NAMES,
    AgentName,
    BossReport,
    DelegationBudget,
    DelegationResult,
    SpecialistReport,
    TeamDeps,
)

READ_TOOLS = {
    "list_open_tickets",
    "get_ticket",
    "check_stock",
    "list_vendors",
    "get_cash_and_obligations",
    "get_pricing",
}

# Least privilege: everyone can read; each role only gets the writes it owns.
AGENT_TOOLS: dict[AgentName, set[str]] = {
    "boss": READ_TOOLS | {"update_ticket"},
    "inventory": READ_TOOLS | {"ship_order", "create_draft"},
    "accounting": READ_TOOLS | {"request_payment", "create_draft"},
    "facilities": READ_TOOLS | {"request_payment", "create_draft"},
    "customer_service": READ_TOOLS | {"create_draft"},
}
assert not any(tools & HUMAN_ONLY_TOOLS for tools in AGENT_TOOLS.values())


async def delegate(ctx: RunContext[TeamDeps], to_agent: AgentName, task: str) -> dict[str, Any]:
    """Hand a task to another team member and get their structured report back.

    Use this when the work belongs to another role (inventory, accounting,
    facilities, customer_service, or boss for final calls). Write a
    self-contained task: include ticket ids, SKUs, sizes, amounts and exactly
    what you need back. The other agent has its own tools; it can't see your
    conversation.
    """
    deps = ctx.deps
    me = deps.current
    error = None
    if to_agent == me:
        error = "You can't delegate to yourself."
    elif to_agent in deps.chain:
        error = f"{to_agent} is already working on this request higher up the chain ({' > '.join(deps.chain)}). Report back instead."
    elif len(deps.chain) >= deps.max_depth:
        error = f"Delegation depth limit ({deps.max_depth}) reached. Do the work yourself or report back."
    elif not deps.budget.take():
        error = f"Team delegation limit ({deps.budget.max_delegations}) reached for this run. Report back with what you have."

    await deps.audit.log(
        run_id=deps.run_id, agent=me, chain=deps.chain, event="delegation",
        to_agent=to_agent, task=short(task), allowed=error is None, error=error,
    )
    if error:
        return DelegationResult(ok=False, to_agent=to_agent, error=error).model_dump()

    output = await run_agent(to_agent, task, deps.child(to_agent), usage=ctx.usage)
    return DelegationResult(ok=True, to_agent=to_agent, report=output.model_dump()).model_dump()


def _build_agent(name: AgentName) -> Agent[TeamDeps, Any]:
    allowed = AGENT_TOOLS[name]
    tools = mcp_toolset().filtered(lambda ctx, tool_def: tool_def.name in allowed)
    return Agent(
        get_model(),
        name=name,
        # Re-read on every run, so prompt edits apply without restarting the backend.
        instructions=lambda: (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8"),
        deps_type=TeamDeps,
        output_type=BossReport if name == "boss" else SpecialistReport,
        tools=[delegate],
        toolsets=[tools],
        retries=AGENT_RETRIES,
        model_settings=MODEL_SETTINGS,
    )


_AGENTS: dict[AgentName, Agent[TeamDeps, Any]] = {}


def get_agent(name: AgentName) -> Agent[TeamDeps, Any]:
    if name not in _AGENTS:
        _AGENTS[name] = _build_agent(name)
    return _AGENTS[name]


def all_agents() -> dict[AgentName, Agent[TeamDeps, Any]]:
    return {name: get_agent(name) for name in AGENT_NAMES}


def _report_digest(output: Any) -> dict[str, Any]:
    """The parts of a final report the dashboard shows, kept short but untruncated mid-JSON."""
    data = output.model_dump()
    keep = ("summary", "decisions", "human_actions_needed") if data.get("agent") == "boss" else (
        "summary", "actions_taken", "needs_human_approval", "blocked_by", "facts")
    digest = {k: data.get(k) for k in keep if data.get(k) not in (None, [])}
    if "facts" in digest:
        digest["facts"] = digest["facts"][:6]
    return digest


async def run_agent(name: AgentName, task: str, deps: TeamDeps, *, usage: RunUsage | None = None) -> Any:
    """Run one agent, logging every loop step to the audit trail."""
    agent = get_agent(name)
    log = deps.audit.log
    ids = dict(run_id=deps.run_id, agent=name, chain=deps.chain)
    await log(**ids, event="agent_start", task=short(task))
    step = 0
    try:
        async with agent.iter(task, deps=deps, usage=usage, usage_limits=TEAM_LIMITS) as run:
            async for node in run:
                if Agent.is_model_request_node(node):
                    step += 1
                    results = [
                        {"tool": p.tool_name, "result": short(p.content)}
                        for p in node.request.parts if isinstance(p, ToolReturnPart)
                    ]
                    retries = [
                        {"tool": p.tool_name, "retry": short(p.content)}
                        for p in node.request.parts if isinstance(p, RetryPromptPart)
                    ]
                    first = any(isinstance(p, UserPromptPart) for p in node.request.parts)
                    await log(**ids, step=step, event="model_request",
                              sends="task" if first else "tool_results",
                              tool_results=results, retries=retries)
                elif Agent.is_call_tools_node(node):
                    resp = node.model_response
                    calls = [
                        {"tool": p.tool_name, "args": short(p.args_as_dict())}
                        for p in resp.parts if isinstance(p, ToolCallPart)
                    ]
                    text = " ".join(p.content for p in resp.parts if isinstance(p, TextPart))
                    await log(**ids, step=step, event="model_response",
                              tool_calls=calls, text=short(text) if text else None,
                              finish_reason=resp.finish_reason,
                              tokens={"in": resp.usage.input_tokens, "out": resp.usage.output_tokens})
                elif Agent.is_end_node(node):
                    pass
            output = run.result.output
    except UsageLimitExceeded as exc:
        await log(**ids, step=step, event="agent_stop", stop_reason="usage_limit_exceeded", error=short(str(exc)))
        raise
    except Exception as exc:
        await log(**ids, step=step, event="agent_stop", stop_reason="error", error=short(f"{type(exc).__name__}: {exc}"))
        raise
    await log(**ids, step=step, event="agent_stop", stop_reason="final_output",
              output=short(output.model_dump(), 600), report=_report_digest(output),
              team_usage_so_far={"requests": run.usage.requests, "tool_calls": run.usage.tool_calls,
                                 "tokens": run.usage.total_tokens})
    return output


def new_run_id() -> str:
    return uuid.uuid4().hex[:12]


async def run_team(
    task: str, *, start_with: AgentName = "boss", audit: AuditTrail | None = None, run_id: str | None = None
) -> tuple[str, Any]:
    """Run the team on a task (normally starting at the boss). Returns (run_id, output)."""
    run_id = run_id or new_run_id()
    deps = TeamDeps(
        run_id=run_id,
        audit=audit or AuditTrail(AUDIT_PATH),
        chain=(start_with,),
        budget=DelegationBudget(MAX_DELEGATIONS),
        max_depth=MAX_DELEGATION_DEPTH,
    )
    # Enter the MCP connection once so every agent in the run shares one server process.
    async with mcp_toolset():
        output = await run_agent(start_with, task, deps, usage=RunUsage())
    return run_id, output
