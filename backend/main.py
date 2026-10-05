"""FastAPI routes for the Campus Customs dashboard.

Run from inside backend/ (with the HW5 venv active):
    uvicorn main:app --reload --port 8000

Shop data is read and changed only through the MCP server (one stdio client
for the API, plus the team's own connection during runs). The only file
operation outside MCP is /api/reset, which copies the original database over
the working copy.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Let `backend.*` imports work when uvicorn is started from inside backend/.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from backend.config import AUDIT_PATH, MODEL_NAME, ORIGINAL_DB, STATE_DIR, WORKING_DB, mcp_client
from backend.models import (
    AgentEvent,
    ApprovalRequest,
    ApprovalResult,
    CashSummary,
    EventList,
    PaymentRequestList,
    RejectRequest,
    ResetRequest,
    ResetResult,
    RunInfo,
    TicketList,
    TicketSummary,
    ToolUse,
)
from backend.team import new_run_id, run_team

DESK_TICKETS = (101, 102, 103)
NON_MCP_TOOLS = {"delegate", "final_result"}

# In-memory run registry (resets when the server restarts). One team run at a time,
# so two runs never race on the same tickets, cash or stock.
RUNS: dict[str, RunInfo] = {}
_active_run: str | None = None
_tasks: set[asyncio.Task] = set()  # keep background runs referenced until they finish


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------- MCP access ----------

@asynccontextmanager
async def lifespan(app: FastAPI):
    client = mcp_client()
    async with client:
        app.state.mcp = client
        app.state.mcp_lock = asyncio.Lock()
        yield


app = FastAPI(title="Campus Customs desk API", version="1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    # Vite dev server; DASHBOARD_ORIGINS (comma-separated) can add more, e.g. for a test port.
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173",
                   *[o.strip() for o in os.getenv("DASHBOARD_ORIGINS", "").split(",") if o.strip()]],
    allow_methods=["*"],
    allow_headers=["*"],
)


async def mcp(tool: str, **args: Any) -> dict:
    """Call one MCP tool and return its structured result."""
    async with app.state.mcp_lock:
        result = await app.state.mcp.call_tool(tool, args, raise_on_error=False)
    if result.is_error:
        raise HTTPException(502, f"MCP tool {tool} failed: {result.content[0].text if result.content else 'unknown error'}")
    return result.structured_content or json.loads(result.content[0].text)


async def _cash() -> CashSummary:
    data = await mcp("get_cash_and_obligations")
    acct = next((a for a in data["cash_accounts"] if a["name"] == "checking"), None)
    if not acct:
        raise HTTPException(404, "No checking account in cash_accounts.")
    pending = round(sum(r["amount"] for r in data["pending_payment_requests"] if r["account"] == "checking"), 2)
    return CashSummary(
        as_of=data["as_of"],
        account="checking",
        balance=acct["balance"],
        balance_date=acct["date"],
        pending_requests_total=pending,
        available_after_pending=round(acct["balance"] - pending, 2),
        unpaid_invoices_total=round(sum(i["amount"] for i in data["unpaid_invoices"]), 2),
        rent_due_total=round(sum(l["monthly_rent"] for l in data["lease_rent_due"]), 2),
        cash_after_all_obligations=data["cash_after_all_obligations"],
        payments=data["payments_recorded"],
    )


def _last_run_for(ticket_id: int) -> str | None:
    runs = [r for r in RUNS.values() if r.ticket_id == ticket_id]
    return max(runs, key=lambda r: r.started_at).run_id if runs else None


# ---------- routes ----------

@app.get("/api/health")
async def health() -> dict:
    tools = await app.state.mcp.list_tools()
    return {
        "ok": True,
        "model": MODEL_NAME,
        "working_db": str(WORKING_DB),
        "mcp_tools": sorted(t.name for t in tools),
        "active_run": _active_run,
    }


@app.get("/api/tickets", response_model=TicketList)
async def list_tickets() -> TicketList:
    """Tickets 101, 102 and 103 with their current status, via MCP get_ticket."""
    details = await asyncio.gather(*(mcp("get_ticket", ticket_id=t) for t in DESK_TICKETS))
    tickets = []
    for d in details:
        if not d.get("ok"):
            continue
        t = d["ticket"]
        tickets.append(TicketSummary(
            **{k: t[k] for k in ("id", "type", "requester", "subject", "status", "sku", "size", "qty", "lease_id", "invoice_id", "created_at")},
            notes=[line for line in (t["notes"] or "").splitlines() if line.strip()],
            pending_payment_requests=[r["id"] for r in d["payment_requests"] if r["status"] == "pending_human_approval"],
            draft_ids=[x["id"] for x in d["drafts"]],
            last_run_id=_last_run_for(t["id"]),
        ))
    return TicketList(today=details[0].get("today") if details else None, tickets=tickets)


@app.get("/api/tickets/{ticket_id}")
async def ticket_detail(ticket_id: int) -> dict:
    """Full ticket detail (linked lease/invoice, payments, requests, drafts), via MCP get_ticket."""
    data = await mcp("get_ticket", ticket_id=ticket_id)
    if not data.get("ok"):
        raise HTTPException(404, data.get("error", "Ticket not found."))
    data["last_run_id"] = _last_run_for(ticket_id)
    return data


def _task_for(ticket_id: int) -> str:
    return (
        f"Work desk ticket {ticket_id}. Read it with get_ticket, delegate only to the specialists it needs, "
        "make the final call, and record it with update_ticket. Follow every shop rule: payments only as "
        "requests for human approval, drafts only (never send), no shipping while a related invoice is unpaid, "
        "and resolve only after rechecking the database shows nothing pending."
    )


async def _execute(run_id: str, ticket_id: int) -> None:
    global _active_run
    info = RUNS[run_id]
    try:
        _, output = await run_team(_task_for(ticket_id), run_id=run_id)
        info.status, info.output = "completed", output.model_dump()
    except Exception as exc:  # recorded for the dashboard; details are also in the audit trail
        info.status, info.error = "failed", f"{type(exc).__name__}: {exc}"
    finally:
        info.finished_at = _now()
        _active_run = None


@app.post("/api/tickets/{ticket_id}/run", response_model=RunInfo, status_code=202)
async def run_ticket(ticket_id: int) -> RunInfo:
    """Start the agent team (boss first) on one ticket. Returns at once; poll /api/runs/{run_id}."""
    global _active_run
    if ticket_id not in DESK_TICKETS:
        raise HTTPException(404, f"Ticket {ticket_id} is not one of the desk tickets {list(DESK_TICKETS)}.")
    if _active_run:
        raise HTTPException(409, f"Run {_active_run} is still going. Wait for it to finish.")
    run_id = new_run_id()
    _active_run = run_id
    RUNS[run_id] = RunInfo(
        run_id=run_id, ticket_id=ticket_id, status="running", started_at=_now(),
        events_url=f"/api/events?run_id={run_id}",
    )
    task = asyncio.create_task(_execute(run_id, ticket_id))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return RUNS[run_id]


@app.get("/api/runs", response_model=list[RunInfo])
async def list_runs() -> list[RunInfo]:
    return sorted(RUNS.values(), key=lambda r: r.started_at, reverse=True)


@app.get("/api/runs/{run_id}", response_model=RunInfo)
async def get_run(run_id: str) -> RunInfo:
    if run_id not in RUNS:
        raise HTTPException(404, f"No run {run_id} since the server started.")
    return RUNS[run_id]


def _to_event(e: dict) -> AgentEvent:
    calls = e.get("tool_calls") or []
    said = e.get("text") or e.get("output")
    delegation = None
    for c in calls:
        if c["tool"] == "final_result":
            said = c["args"]
    if e["event"] == "delegation":
        delegation = {k: e.get(k) for k in ("to_agent", "task", "allowed", "error")}
    mcp_tools = [ToolUse(tool=c["tool"], args=c["args"]) for c in calls if c["tool"] not in NON_MCP_TOOLS]
    mcp_tools += [ToolUse(tool=r["tool"], result=r["result"]) for r in e.get("tool_results") or [] if r["tool"] not in NON_MCP_TOOLS]
    run = RUNS.get(e["run_id"])
    return AgentEvent(
        ts=e["ts"], run_id=e["run_id"], ticket_id=run.ticket_id if run else None,
        agent=e["agent"], chain=e["chain"], depth=e["depth"], step=e.get("step"), type=e["event"],
        said=said, mcp_tools=mcp_tools, delegation=delegation,
        stop_reason=e.get("stop_reason"), finish_reason=e.get("finish_reason"), report=e.get("report"),
    )


@app.get("/api/events", response_model=EventList)
async def recent_events(
    limit: int = Query(100, ge=1, le=1000),
    run_id: str | None = None,
    agent: str | None = None,
) -> EventList:
    """Most recent agent-loop events from output/audit_trail.json, oldest first."""
    raw = json.loads(AUDIT_PATH.read_text(encoding="utf-8") or "[]") if AUDIT_PATH.exists() else []
    if run_id:
        raw = [e for e in raw if e["run_id"] == run_id]
    if agent:
        raw = [e for e in raw if e["agent"] == agent]
    return EventList(total=len(raw), events=[_to_event(e) for e in raw[-limit:]])


@app.get("/api/cash", response_model=CashSummary)
async def cash() -> CashSummary:
    """Checking balance from cash_accounts, plus pending requests and obligations, via MCP."""
    return await _cash()


@app.get("/api/payment-requests", response_model=PaymentRequestList)
async def payment_requests() -> PaymentRequestList:
    """Payment/purchase requests the agents created that are waiting for a human."""
    data = await mcp("get_cash_and_obligations")
    return PaymentRequestList(pending=data["pending_payment_requests"], cash=await _cash())


@app.post("/api/payment-requests/{request_id}/approve", response_model=ApprovalResult)
async def approve(request_id: str, body: ApprovalRequest) -> ApprovalResult:
    """HUMAN approval. The only route that moves money: records the payment and reduces cash (MCP approve_payment)."""
    result = await mcp("approve_payment", request_id=request_id, approved_by=body.approved_by)
    if not result.get("ok"):
        raise HTTPException(409, result.get("error", "Approval refused."))
    return ApprovalResult(ok=True, request=result["request"], payment_id=result["payment_id"], cash=await _cash())


@app.post("/api/payment-requests/{request_id}/reject", response_model=ApprovalResult)
async def reject(request_id: str, body: RejectRequest) -> ApprovalResult:
    """HUMAN rejection. Nothing is paid (MCP reject_payment)."""
    result = await mcp("reject_payment", request_id=request_id, rejected_by=body.rejected_by, reason=body.reason)
    if not result.get("ok"):
        raise HTTPException(409, result.get("error", "Rejection refused."))
    return ApprovalResult(ok=True, request=result["request"], cash=await _cash())


@app.post("/api/reset", response_model=ResetResult)
async def reset(body: ResetRequest) -> ResetResult:
    """Copy data/campus_customs.db over the working copy and clear drafts/payment requests."""
    if not body.confirm:
        raise HTTPException(400, 'Send {"confirm": true} to reset the working database.')
    if _active_run:
        raise HTTPException(409, f"Run {_active_run} is still going. Reset after it finishes.")
    if WORKING_DB == ORIGINAL_DB.resolve():
        raise HTTPException(500, "Working database points at the original. Refusing to reset.")
    async with app.state.mcp_lock:  # no MCP call can read the file mid-copy
        tmp = WORKING_DB.with_suffix(".db.tmp")
        shutil.copyfile(ORIGINAL_DB, tmp)
        tmp.replace(WORKING_DB)
        cleared = []
        for leftover in (WORKING_DB.with_name(WORKING_DB.name + "-wal"), WORKING_DB.with_name(WORKING_DB.name + "-shm")):
            if leftover.exists():
                leftover.unlink()
                cleared.append(leftover.name)
        names = ["drafts.json", "payment_requests.json"]
        if body.clear_audit_trail:
            names.append(AUDIT_PATH.name)
        for name in names:
            path = AUDIT_PATH if name == AUDIT_PATH.name else STATE_DIR / name
            if path.exists():
                path.unlink()
                cleared.append(name)
    # Earlier runs describe a database state that no longer exists, so the dashboard shouldn't show them.
    RUNS.clear()
    digest = _sha256(WORKING_DB)
    return ResetResult(
        ok=True, working_db=str(WORKING_DB), sha256=digest,
        matches_original=digest == _sha256(ORIGINAL_DB), cleared=cleared,
    )
