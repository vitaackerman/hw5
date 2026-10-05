# HW5: Campus Customs multi-agent operations desk

A boss agent and four specialist agents (inventory, accounting, facilities, customer service) work the shop's desk tickets. All shop data is read and changed through an MCP server, a FastAPI backend runs the team, and a React dashboard lets a human manager watch the agents and approve payments.

- **Model:** every agent uses `gpt-6-luna` through Portkey (`PORTKEY_API_KEY`).
- **Database:** `data/campus_customs.db` is the original and is never modified. All runs use the working copy `data/campus_customs_new.db`.

```
mcp_server/server.py   MCP server (FastMCP): 12 tools over data/campus_customs_new.db
backend/               PydanticAI agents (team.py), shared types (models.py), prompts/, FastAPI app (main.py)
frontend/              React + Vite + TypeScript dashboard
output/                harness, smoke test, desk tickets (expected/actual/cash/reflection), design, resolved board, audit trail
```

The committed `data/campus_customs_new.db` is the end state of the real three-ticket run (all three tickets resolved, $160.00 in checking). Reset it before running the tickets again.

## 1. Setup (once)

Requires Python 3.11+ (tested with 3.14) and Node 20+ (tested with 24).

From the `hw5/` folder:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
```

Then open `.env` and paste your Portkey key after `PORTKEY_API_KEY=`. `.env` is git-ignored.

Install the frontend packages:

```bash
cd frontend && npm install
```

## 2. Get a clean working database

The working copy has to start from the original values for a full run. With the backend stopped, copy the original over it and clear the leftover drafts and payment requests:

```bash
cp data/campus_customs.db data/campus_customs_new.db
rm -f output/drafts.json output/payment_requests.json
```

If the backend is already running, use the reset route instead (step 5).

## 3. MCP server

The backend starts the MCP server on its own: it launches `mcp_server/server.py` over stdio with the venv's Python. There's nothing separate to start for the app.

To run it by hand, for example to attach another MCP client:

```bash
.venv/bin/python mcp_server/server.py
```

It talks over stdio, so it just waits for a client. Claude Code picks it up from `.mcp.json` as the `campus-customs` server.

## 4. Backend (FastAPI, port 8000)

```bash
cd backend
source ../.venv/bin/activate
uvicorn main:app --reload --port 8000
```

API docs are at http://localhost:8000/docs. Check it's up with `GET /api/health`.

## 5. Reset before a full three-ticket run

With the backend running, this copies the original database over the working copy, checks that their hashes match, clears drafts and payment requests, and forgets earlier runs:

```bash
curl -X POST localhost:8000/api/reset -H 'content-type: application/json' -d '{"confirm": true}'
```

Add `"clear_audit_trail": true` to also start `output/audit_trail.json` fresh. After a reset, checking is $3,400.00 and tickets 101, 102 and 103 are `open`.

## 6. Dashboard (React, port 5173)

```bash
cd frontend
npm run dev
```

Open http://localhost:5173. It has to be port 5173, because that's the origin the backend allows.

Running the tickets:
1. **Dispatch:** click a ticket on the rail, then **Send the team to 101**. The live floor shows which agent is active, its handoffs and its MCP tool calls. The shift report appears when the run finishes.
2. **Approve payments:** when an agent requests a payment, it appears under **Needs your sign-off**. Type your name and click **Approve & pay**. Only this human step changes cash; agents can never move money.
3. **Recheck:** after approving, click **Send the team back to …** so the boss can recheck the database and resolve the ticket.

Ticket statuses, the checking balance and approvals all come from the database through the backend.

There's also a command-line route to the same flow. From `hw5/`:
- `.venv/bin/python -m backend.run "…"` runs the team on a task.
- `.venv/bin/python -m backend.approve list` lists payment requests, and `… approve PR-1 --by "Your Name"` approves one.

## Outputs

- `output/harness.md`: database tables, all MCP tools, the 5 agents, API routes, dashboard, audit trail, safety rules and limits.
- `output/mcp_smoke.json`: MCP tools called through Claude Code and checked against the database.
- `output/desk_tickets.html`: Expected and Actual for each ticket, plus the Cash and Reflection tabs. Double-click to open.
- `output/design.md`: dashboard design notes.
- `output/resolved_tickets.json` and `output/resolved_board.html`: real-run results with dashboard screenshots in `output/screenshots/`.
- `output/audit_trail.json`: every agent-loop step, appended as the agents run.
- `output/github_url.txt`: this repo's URL.
