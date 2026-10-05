# Campus Customs Database Harness

Source: `data/campus_customs.db` (read-only original). Working copy: `data/campus_customs_new.db`. The copy is byte-identical to the original (both SHA-256 `23686a90…3f321f360a`).

## Tables

### `desk` (1 row)
Fields: `date_today`, `notes`
Why it matters: sets the shop's "today" (2026-08-31), which all agents use to judge due dates and urgency.

### `inventory` (10 rows; primary key `sku` + `size`)
Fields: `sku`, `name`, `size`, `qty`, `location`
Why it matters: the inventory agent checks this table to see whether each item and size is in stock and where it is shelved.

### `pricing` (4 rows; primary key `sku`)
Fields: `sku`, `unit_cost`, `list_price`
Why it matters: accounting and customer service use cost and list price to quote prices and check that any discount still leaves a margin.

### `vendors` (3 rows)
Fields: `id`, `name`, `specialty`, `lead_days`
Why it matters: shows who can restock or deliver items and how long each takes, which the inventory and facilities agents need for reorders.

### `leases` (1 row)
Fields: `id`, `space_name`, `landlord`, `monthly_rent`, `next_due`, `notes`
Why it matters: the facilities agent tracks the shop's rent obligation and its due date here.

### `cash_accounts` (1 row; primary key `name`)
Fields: `name`, `balance`, `date`
Why it matters: accounting has to confirm there is enough cash before it approves any payment.

### `payments` (0 rows)
Fields: `id`, `kind`, `ref_id`, `amount`, `account`, `paid_at`, `approved_by`
Why it matters: this is the audit log where agents record approved payments. `kind` + `ref_id` point to whatever was paid (for example a lease or an invoice), and `approved_by` names who approved it.

### `invoices` (1 row; `vendor_id` → `vendors.id`)
Fields: `id`, `vendor_id`, `amount`, `due_date`, `status`, `description`
Why it matters: holds the vendor bills that accounting must pay or track.

### `tickets` (3 rows; `lease_id` → `leases.id`, `invoice_id` → `invoices.id`)
Fields: `id`, `type`, `requester`, `subject`, `sku`, `size`, `qty`, `lease_id`, `invoice_id`, `status`, `notes`, `created_at`
Why it matters: the boss agent's work queue. Each ticket's `type` decides which specialist agent handles it.

Note: `sku` in `tickets` and `pricing` links to `inventory` by convention only. There is no foreign key on it, so agents must check that the SKU exists themselves.

## The three open tickets (not solved yet)

### Ticket 101: `customer_order`, Tauhid Zaman, CC-TEE-WHITE size S, qty 1
- `inventory`: CC-TEE-WHITE size S has qty **0** (Aisle B), so the order can't be filled from stock.
- `invoices` 501 (linked by `invoice_id`): Bulldog Print Co, $840, "Rush reprint CC-TEE-WHITE S", due 2026-08-28, status `open`. It is already past due as of 2026-08-31.
- `vendors` 1: Bulldog Print Co, apparel reprint, 5 lead days. `pricing`: list price $28.
- Will likely need: inventory, accounting (the overdue invoice) and customer service (reply to the customer with an ETA).

### Ticket 102: `rent_notice`, Elm City Properties, lease 1
- `leases` 1: Chapel Street shop, $2,400/month, next due 2026-09-02 (2 days after `date_today`).
- `cash_accounts`: checking $3,400 as of 2026-08-31. `payments` is empty, so rent has not been paid yet.
- Will likely need: facilities and accounting (a payment row plus updates to the balance and due date).
- Cash constraint across tickets: rent $2,400 + invoice 501 $840 = $3,240, which leaves only $160 in checking.

### Ticket 103: `price_override`, Yale AI Club, CC-HOOD-NAVY size M, qty 20, bulk discount request
- `inventory`: CC-HOOD-NAVY size M has qty **8** (Aisle A), 12 short of the 20 requested. Other sizes: S 4, L 14, XL 6.
- `pricing`: unit cost $22, list price $58. Any discount needs to stay above cost.
- `vendors` 1: Bulldog Print Co (apparel reprint, 5 lead days) could cover the shortfall.
- Will likely need: customer service, accounting (whether to approve the discount and at what margin) and inventory (the stock shortfall).

## Problem 3: MCP server tools

The FastMCP server is in `mcp_server/server.py`. It opens `data/campus_customs_new.db` read-only.

### `check_stock(sku, size)`
- Tables read: `inventory`, `tickets`, `invoices`, `vendors`, `desk`
- Helps unlock: tickets 101 and 103
- Why: it shows that the white tee in size S has 0 in stock and that rush reprint invoice 501 is overdue (ticket 101), and that navy hoodies in size M have only 8 against the 20 requested, with vendor lead times for a restock (ticket 103).

### `get_cash_and_obligations()`
- Tables read: `cash_accounts`, `invoices`, `vendors`, `leases`, `payments`, `desk`
- Helps unlock: ticket 102
- Why: it puts the $2,400 rent due in 2 days next to the $3,400 checking balance and the overdue $840 invoice, so the agents can see that paying both leaves only $160.

### `get_pricing(sku, qty)`
- Tables read: `pricing`, `inventory`
- Helps unlock: ticket 103
- Why: it gives the hoodie's $22 cost, $58 list price, margin and 20-unit totals, so the agents can judge how much of a bulk discount still covers cost.

## Problem 5: Agent team and expanded MCP server

The agent code is in `backend/` (`team.py`, `models.py`, `config.py`, `audit.py`), with one prompt per agent in `backend/prompts/`. Every agent is a PydanticAI agent on `gpt-6-luna` through Portkey (`PORTKEY_API_KEY`), using the OpenAI Responses API.

### Agents and roles
| Agent | Role |
|-------|------|
| **boss** | Reads the ticket queue, decides who works each ticket, weighs the reports, and makes the final calls (including the discount level). It is the only agent that changes ticket status, and it rechecks the database before resolving. |
| **inventory** | Stock levels, shortfalls, and restock ETAs from vendor `lead_days`. Ships customer orders only when told to and when no invoice for the product is unpaid. Drafts vendor messages. |
| **accounting** | Cash, invoices, competing bills, and margin and discount math. Creates invoice payment requests for human approval. |
| **facilities** | The lease, rent due date and landlord. Creates rent payment requests for human approval and drafts landlord messages. |
| **customer_service** | Customer and student-group replies, saved only as `customer_email` drafts. It uses only tool-backed facts and never mentions costs or cash. |

**Full connectivity:** every agent has the same `delegate(to_agent, task)` tool, so any agent can hand work to any other. Delegating to yourself, or to an agent already earlier in the chain (a cycle), is refused.

### MCP tools and the tables they use
| Tool | Tables / files | Who can call it |
|------|----------------|-----------------|
| `list_open_tickets` | desk, tickets | all agents |
| `get_ticket` | desk, tickets, leases, invoices, vendors, payments (+ payment_requests.json, drafts.json) | all agents |
| `check_stock` | inventory, tickets, invoices, vendors, desk | all agents |
| `list_vendors` | vendors | all agents |
| `get_cash_and_obligations` | desk, cash_accounts, invoices, vendors, leases, payments (+ payment_requests.json) | all agents |
| `get_pricing` | pricing, inventory | all agents |
| `create_draft` | drafts.json only | inventory, accounting, facilities, customer_service |
| `request_payment` | reads desk, cash_accounts, invoices, leases; writes payment_requests.json only | accounting, facilities |
| `ship_order` | reads tickets, invoices; writes inventory.qty, tickets.notes | inventory |
| `update_ticket` | tickets (status, notes) | boss |
| `approve_payment` | desk, cash_accounts, payments, invoices, leases (+ payment_requests.json) | human only (`backend/approve.py`) |
| `reject_payment` | payment_requests.json only | human only |

### Safety
- **Customer communication:** no tool can send anything. Customers, vendors and the landlord get `create_draft` entries marked `draft_not_sent` for a human to review and send. Customer service may quote only tool-backed prices and dates, never a discount the boss hasn't approved, and never internal costs, cash or invoices.
- **Inventory changes:** the only write to stock is `ship_order`. It refuses while any invoice for that product is unpaid, when stock is short, or when the order was already shipped. There's no tool to add stock, so agents can't claim a delivery arrived. ETAs are `desk.date_today` + the vendor's `lead_days`.
- **Real-money actions:** agents can only call `request_payment`, which validates the amount, prevents duplicates and checks cash net of other pending requests, but changes no cash, `payments` rows or bills. Only a human running `approve_payment` (and not under an agent's name) moves money, in one transaction with a recheck. No tool adds cash, since cash only goes out. Tickets can't be resolved while a payment request is pending, and the boss must recheck with `get_ticket` first.
- **Audit:** every agent-loop step is appended to `output/audit_trail.json`: agent, delegation chain, model requests, tool calls with short args, tool results, delegations (allowed or refused), finish and stop reasons, and token usage. Model reasoning ("thinking") is never stored.

### Practical limits (one budget per team run, shared by all agents)
- 40 model requests, 60 tool calls and 400,000 total tokens across all agents (`UsageLimits`, with sub-agents sharing the parent's usage).
- At most 8 delegations per run, and a delegation chain at most 3 agents deep (for example boss > inventory > accounting).
- 2 retries per agent for bad tool arguments or output, and 1 retry per MCP tool error.
- Each model response is capped at 8,000 tokens with a 120 s timeout. Audit text is truncated to 300 characters per field.
- Prompts tell agents to keep delegations few, avoid repeating tool calls, and stop and report when a rule blocks progress.

## Problem 7: FastAPI routes for the dashboard

The API is `backend/main.py`. Run it from inside `backend/` with the HW5 venv active: `uvicorn main:app --reload --port 8000`. Every shop read and change goes through the MCP server. The only exception is `/api/reset`, which copies the original database file. A team run on one ticket at a time.

- `GET /api/health`: shows the API is up, with the model, the working database path, the MCP tools available and any active run.
- `GET /api/tickets`: tickets 101, 102 and 103 with current status, notes, pending payment request ids, draft ids and last run id (via MCP `get_ticket`).
- `GET /api/tickets/{ticket_id}`: full detail for one ticket: linked lease or invoice, payments, payment requests and drafts (via MCP `get_ticket`).
- `POST /api/tickets/{ticket_id}/run`: starts the agent team (boss first) on ticket 101, 102 or 103 in the background and returns a `run_id` right away (202). Returns 409 if a run is already going.
- `GET /api/runs`: every run started since the server started, newest first.
- `GET /api/runs/{run_id}`: one run's status (running, completed or failed) and the boss's final `BossReport`.
- `GET /api/events?limit=&run_id=&agent=`: recent agent events from `output/audit_trail.json`: which agent acted, its delegation chain, what it said, the MCP tools it called (args) or got back (results), delegations and stop reasons.
- `GET /api/cash`: the checking balance from `cash_accounts`, plus pending request totals, unpaid invoices, rent due and cash left after all obligations (via MCP `get_cash_and_obligations`).
- `GET /api/payment-requests`: payment and purchase requests the agents created that are waiting for a human, with the cash summary.
- `POST /api/payment-requests/{request_id}/approve`: **human approval** (`{"approved_by": "<your name>"}`). It is the only route that moves money: it records the payment, reduces cash, and marks the invoice paid or advances the lease (via the human-only MCP `approve_payment`). Agent names are refused.
- `POST /api/payment-requests/{request_id}/reject`: human rejection (`{"rejected_by", "reason"}`). Nothing is paid (via MCP `reject_payment`).
- `POST /api/reset`: with `{"confirm": true}`, copies `data/campus_customs.db` over `data/campus_customs_new.db`, verifies the hashes match, clears `drafts.json` and `payment_requests.json`, and forgets earlier runs on the dashboard. With `"clear_audit_trail": true` it also clears `audit_trail.json`. Refused while a run is going.

## Problem 8: Dashboard

The React + Vite + TypeScript dashboard is in `frontend/`. Run it with `npm run dev` on `http://localhost:5173`, the origin the backend's CORS allows. It uses only the Problem 7 routes; ticket status, cash and approvals always come from the backend, never from state invented in the browser. Design notes are in `output/design.md`.
- **Till:** the checking balance from `cash_accounts`, with a receipt tape of pending requests, obligations and recorded payments. After an approval it counts down to the new balance.
- **Sign-off tray:** pending payment requests. A human types a name and clicks **Approve & pay**, which calls `POST /api/payment-requests/{id}/approve`. That is the only way money moves.
- **Ticket rail and file:** status pills come straight from `tickets.status`. The file shows the agents' notes, drafts marked "Not sent", and a dispatch button that locks during a run, so you can't start two.
- **Live floor and shift report:** polls `/api/events?run_id=` every 1.2 s. The boss wears a navy manager badge, and each specialist has a department color. The live view shows the active agent, what it's doing, its handoffs and its exact MCP tool calls, then one summary per agent when the run ends.

## Problem 9: Full system and real run

### The complete system
| Layer | What it is | Where it's documented in this file |
|---|---|---|
| Database | `data/campus_customs.db` (original, never modified) and `data/campus_customs_new.db` (working copy). Tables: `desk`, `inventory`, `pricing`, `vendors`, `leases`, `cash_accounts`, `payments`, `invoices`, `tickets` | Tables |
| MCP server | `mcp_server/server.py`, 12 tools: 6 read, 4 agent write, 2 human-only (`approve_payment`, `reject_payment`) | Problem 5: MCP tools and the tables they use |
| Agents | 5 PydanticAI agents on `gpt-6-luna` through Portkey (Responses API): boss, inventory, accounting, facilities, customer_service, with any-to-any `delegate` | Problem 5: Agents and roles |
| API | `backend/main.py`, 12 FastAPI routes | Problem 7 |
| Dashboard | `frontend/` React app | Problem 8, plus `output/design.md` |
| Audit trail | `output/audit_trail.json` | below |

### Audit trail
- **What's logged:** every agent-loop step is appended as JSON with timestamp, `run_id`, agent, delegation chain and depth, step and event type (`agent_start`, `model_request`, `model_response`, `delegation`, `agent_stop`).
- **What each entry can include:** tool calls with short args, tool results, delegations (allowed or refused, with the reason), finish and stop reasons, token usage so far, and on `agent_stop` the agent's final summary, actions, approvals needed and blockers.
- **What's never stored:** model reasoning ("thinking") parts.
- **This run's entries** are 105–307 of `output/audit_trail.json` (203 entries across 7 team runs). Entries 1–104 are earlier practice runs, and entries after 307 are a later practice run (done after a reset); both are kept because the trail is append-only. The committed `data/campus_customs_new.db` is the Problem 9 end state.

### Safety rules, as enforced in the final system
- **Today** is `desk.date_today` (2026-08-31), not the real date. Vendor lead times come only from `vendors`, and ETAs are worded as estimates.
- **No shipping while a related invoice is unpaid.** `ship_order` refuses in code. It also refuses when stock is short, and nothing can add stock.
- **Payments need a human.** Agents can only `request_payment`, which changes no cash, payment rows or bills. `approve_payment` is human-only and never offered to agents; it runs from the dashboard or `backend/approve.py`, rejects agent names, and rechecks before paying in one transaction.
- **Cash only goes out.** No tool records income.
- **No contact with anyone.** Customers, vendors and the landlord only get `create_draft` entries marked `draft_not_sent`.
- **No resolving without a recheck.** `update_ticket` refuses `resolved` while a request is pending, and the boss must recheck with `get_ticket` first.
- **What "resolved" means** (added to `backend/prompts/boss.md` during this run): everything the team controls is done and rechecked. That means payments approved and recorded, the needed drafts saved, and the decision noted. Outside waits, like deliveries, customer replies or a human sending drafts, are named in the closing note. Resolving never claims stock arrived or a message was sent.
- **The original database is never written.** The server refuses to open it, and `/api/reset` only copies from it.

### Real run results (2026-10-05)
| Ticket | Final status | Team runs | Human approval | Cash change |
|---|---|---|---|---|
| 101 | resolved | 3 (`6a5a81cfb41c`, `8bea79de4fb5`, `7b647c0d2349`) | PR-1, $840.00, invoice 501 | −$840.00 |
| 102 | resolved | 2 (`6e52812f55a4`, `1bc8f481358d`) | PR-2, $2,400.00, rent lease 1 | −$2,400.00 |
| 103 | resolved | 2 (`b602b7c8541d`, `df4457a353c0`) | none | $0.00 |

Checking went from $3,400.00 to **$160.00**, verified in `cash_accounts`. Details are in `output/desk_tickets.html` (Actual and Cash tabs), `output/resolved_tickets.json` and `output/resolved_board.html`.

**Known gap found by the run:** for ticket 102, facilities, not accounting, created the rent payment request. Facilities still has `request_payment` and its prompt tells it to use it, so the corrected Problem 6 plan (accounting prepares every payment) isn't enforced yet.
