"""Shared structured types for the Campus Customs agent team."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from backend.audit import AuditTrail

AgentName = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]
AGENT_NAMES: tuple[AgentName, ...] = ("boss", "inventory", "accounting", "facilities", "customer_service")

TicketStatus = Literal["open", "in_progress", "waiting_on_approval", "resolved", "unchanged"]


@dataclass
class DelegationBudget:
    """Shared across one team run so delegation can't fan out without limit."""

    max_delegations: int
    used: int = 0

    def take(self) -> bool:
        if self.used >= self.max_delegations:
            return False
        self.used += 1
        return True


@dataclass
class TeamDeps:
    """Passed to every agent run. `chain` is who called whom, ending with the current agent."""

    run_id: str
    audit: AuditTrail
    chain: tuple[AgentName, ...]
    budget: DelegationBudget
    max_depth: int = field(default=3)

    @property
    def current(self) -> AgentName:
        return self.chain[-1]

    def child(self, agent: AgentName) -> TeamDeps:
        return TeamDeps(self.run_id, self.audit, (*self.chain, agent), self.budget, self.max_depth)


class SpecialistReport(BaseModel):
    """What inventory, accounting, facilities and customer service hand back."""

    agent: AgentName
    ticket_ids: list[int] = Field(default_factory=list, description="Tickets this report is about.")
    summary: str = Field(description="One or two sentences answering the task.")
    facts: list[str] = Field(
        default_factory=list,
        description="Facts read from MCP tools, with exact values (dates, qty, $). No guesses.",
    )
    actions_taken: list[str] = Field(
        default_factory=list,
        description="Write tools actually called and their result, e.g. 'request_payment PR-1 created'. Empty if read-only.",
    )
    needs_human_approval: list[str] = Field(
        default_factory=list, description="Anything waiting on a human, e.g. a pending payment request id."
    )
    recommended_next_steps: list[str] = Field(default_factory=list)
    blocked_by: list[str] = Field(
        default_factory=list, description="Rules or missing data that stop progress, e.g. 'invoice 501 unpaid'."
    )


class TicketDecision(BaseModel):
    ticket_id: int
    assigned_to: list[AgentName] = Field(description="Agents the boss sent work to for this ticket.")
    decision: str = Field(description="The boss's call for this ticket, with the key numbers behind it.")
    status_after: TicketStatus = Field(description="Ticket status in the database after this run.")
    waiting_on: list[str] = Field(default_factory=list, description="Human approvals, deliveries, or replies still needed.")


class BossReport(BaseModel):
    """The boss's final answer for a run."""

    agent: Literal["boss"] = "boss"
    summary: str
    decisions: list[TicketDecision] = Field(default_factory=list)
    human_actions_needed: list[str] = Field(
        default_factory=list, description="Approvals or sends only a human can do, e.g. 'approve PR-1'."
    )


class DelegationResult(BaseModel):
    """What the delegate tool returns to the calling agent."""

    ok: bool
    to_agent: AgentName
    report: dict | None = None
    error: str | None = None


# ---------- API (FastAPI) request/response types for the dashboard ----------

RunStatus = Literal["running", "completed", "failed"]


class TicketSummary(BaseModel):
    id: int
    type: str
    requester: str
    subject: str
    status: str
    sku: str | None = None
    size: str | None = None
    qty: int | None = None
    lease_id: int | None = None
    invoice_id: int | None = None
    created_at: str
    notes: list[str] = Field(default_factory=list, description="Ticket notes, one per line, oldest first.")
    pending_payment_requests: list[str] = Field(default_factory=list, description="Ids like PR-1 still waiting for a human.")
    draft_ids: list[str] = Field(default_factory=list)
    last_run_id: str | None = Field(None, description="Most recent team run on this ticket started from this API.")


class TicketList(BaseModel):
    today: str | None
    tickets: list[TicketSummary]


class RunInfo(BaseModel):
    run_id: str
    ticket_id: int
    status: RunStatus
    started_at: str
    finished_at: str | None = None
    output: dict | None = Field(None, description="The boss's BossReport when status is completed.")
    error: str | None = None
    events_url: str


class ToolUse(BaseModel):
    tool: str
    args: str | None = None
    result: str | None = None


class AgentEvent(BaseModel):
    ts: str
    run_id: str
    ticket_id: int | None = None
    agent: str
    chain: str
    depth: int
    step: int | None
    type: str = Field(description="agent_start | model_request | model_response | delegation | agent_stop")
    said: str | None = Field(None, description="What the agent said: its text or final report (truncated).")
    mcp_tools: list[ToolUse] = Field(default_factory=list, description="MCP tool calls requested, or MCP results received.")
    delegation: dict | None = Field(None, description="to_agent, task, allowed, error for delegation events.")
    stop_reason: str | None = None
    finish_reason: str | None = None
    report: dict | None = Field(None, description="On agent_stop: the agent's final summary, actions, approvals needed.")


class EventList(BaseModel):
    total: int
    events: list[AgentEvent]


class CashSummary(BaseModel):
    as_of: str | None
    account: str
    balance: float
    balance_date: str
    pending_requests_total: float
    available_after_pending: float
    unpaid_invoices_total: float
    rent_due_total: float
    cash_after_all_obligations: float
    payments: list[dict] = Field(default_factory=list, description="Payments recorded in the payments table, oldest first.")


class PaymentRequestList(BaseModel):
    pending: list[dict]
    cash: CashSummary


class ApprovalRequest(BaseModel):
    approved_by: str = Field(min_length=1, description="The human approving. Agent names are refused.")


class RejectRequest(BaseModel):
    rejected_by: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class ApprovalResult(BaseModel):
    ok: bool
    request: dict
    payment_id: int | None = None
    cash: CashSummary


class ResetRequest(BaseModel):
    confirm: bool = Field(description="Must be true. Overwrites the working database with the original.")
    clear_audit_trail: bool = False


class ResetResult(BaseModel):
    ok: bool
    working_db: str
    sha256: str
    matches_original: bool
    cleared: list[str]
