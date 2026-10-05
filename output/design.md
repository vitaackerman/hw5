# Campus Customs ops desk: dashboard design

The dashboard (`frontend/`, React + Vite + TypeScript) is the store manager's desk for the Chapel Street shop. It talks only to the Problem 7 FastAPI routes at `http://localhost:8000`. Every ticket status, cash figure and approval it shows comes from the backend, which reads the database through the MCP server. Nothing is faked in the browser.

## Idea
Instead of an admin template, the screen is laid out like the back office of a campus shop:
- **Tickets** are order slips clipped to a rail.
- **AI agents** are staff wearing lanyard badges.
- **Cash** is a register till with a receipt tape.
- **Approvals** sit in a sign-off tray where a human stamps them.

The visual language carries over from `output/desk_tickets.html`: Yale-navy ink on a steel-grey desk, canary paper for things that need a human, and a red rubber stamp for approval. The plan and the dashboard read as one system.

## Layout
```
┌ Campus Customs ops desk ─────────── desk date │ resolved x of 3 │ API ┐
├─────────────── money ───────┬──────────────── work ─────────────────┤
│ TILL  checking balance      │ TICKET RAIL  [101] [102] [103]         │
│       receipt tape          │ TICKET FILE  facts, notes, drafts,     │
│                             │              "Send the team" button    │
│ SIGN-OFF TRAY               │ ON THE FLOOR staff badges + live log   │
│   pending payment slips     │ SHIFT REPORT boss's call + one card    │
│   [Approve & pay]           │              per specialist            │
└─────────────────────────────┴────────────────────────────────────────┘
```
- **Money lives on the left and stays pinned** while you scroll, so cash and approvals are always in view. The work flows top to bottom on the right, in the order a manager deals with it: pick a ticket, read the file, dispatch the team, watch, read the report.
- **On narrow screens** the columns stack: till, tray, rail, file, floor, report.

## Agents: boss versus specialists
- **The boss gets the manager badge.** It's larger, with a navy band trimmed in Yale gold, a gold-ringed monogram and the label "Manager". It sits on its own to the left of the roster, so the chain of command is visible at a glance.
- **Each specialist has a department color**, used everywhere that agent appears: its badge band, its log stripe, its chips and its shift-report card.

| Agent | Department | Color |
|---|---|---|
| Inventory | Stockroom | teal `#0E7C86` |
| Accounting | Back office ledger | violet `#5B3A9E` |
| Facilities | Lease & building | brass `#8C6300` |
| Customer service | Front counter | raspberry `#B8336A` |

These colors are kept clear of the status colors: red means a human is needed, green means paid or resolved.

**While a run is going:**
- **Badge states:**
  - The active agent's badge lifts, turns full color, and its monogram pulses.
  - Agents waiting on a teammate they delegated to show "Waiting".
  - Everyone else is dimmed, labeled "Off the floor".
- **"Now working" line:** says in plain words who is active and what they're doing, for example "Accounting is working: Using request_payment".
- **Live log:** reads like a shift log:
  - Each line has the agent's color stripe and is indented one step per delegation level, so boss → accounting → … shows as nesting.
  - Lines cover clocking in, handoffs (with the exact task), MCP tool calls (exact tool name and arguments, plus a plain hint like "checked the shelves"), short tool results, and "reported back" with the agent's summary.
  - A refused delegation shows in red with the reason.

## Ticket states
The dashboard reads states from the `tickets` table and shows them the same way on the rail, the ticket file and the shift report:
- **Open:** navy outline pill.
- **In progress:** solid navy pill.
- **Waiting on you** (`waiting_on_approval`): red pill. The rail slip also shows "N to sign" when that ticket has payment requests in the tray.
- **Resolved:** a green stamp, slightly rotated like a real rubber stamp. The slip turns pale green and its title fades. The top bar counts "Resolved x of 3".

The ticket file also shows the notes the boss and other agents appended to the ticket, and any drafts with a **Not sent** tag, so the manager sees exactly what the team left for them.

## Cash
- **The till is the most prominent element on the page.** It's a navy register with the checking balance from `cash_accounts` in large slab digits.
- **After a human approval** the number counts down to the new balance, briefly turns gold, and shows "−$840.00 just now". The payment is added to the "Paid out" section of the tape with the approver's name and date.
- **The receipt tape** lists what's waiting for approval, what's free after approvals, unpaid invoices, rent coming due, and what's left if every bill is paid. That last figure turns red when it gets thin, as it does at $160.
- **Explicit messaging:** "Money only leaves after you approve it." No agent action can change the till. Only the sign-off tray's approve route does.

## Human approvals
- **Each payment request is a canary slip** showing what it pays (vendor invoice or rent), the amount, the reason, the request id, due date, ticket and the requesting agent's chip.
- **Signing is a deliberate act.** Type your name on the "Signing as" line (remembered in this browser), then press the red **Approve & pay $X** stamp. Without a name the stamp stays disabled and the slip says why.
- **Rejecting takes two steps** and needs a reason. A message confirms the result ("PR-1 approved. $840.00 paid from checking." or "Nothing was paid.").

## Staying clear while agents run
- **One run at a time.** The dispatch button locks immediately when clicked and changes to "Dispatching…", then "Team is working this ticket" with a spinner. Every other ticket's button reads "Team is busy on another ticket". A second click does nothing, and the backend would return 409 anyway.
- **The live view updates every 1.2 s while a run is going**, and the approvals tray stays current mid-run. When the run ends, tickets, cash and approvals all refresh from the backend.
- **A page reload during a run reattaches to it**, using `/api/health`'s `active_run`.
- **If the backend is down**, the API status turns red and the page says exactly which command starts it.

## Creative choices that make it pleasant to use
- **Familiar objects** carry meaning without a legend: slips on a rail, staff badges, a till with a tape, and a stamp for sign-off.
- **Typography:** Zilla Slab, a collegiate slab face, for headings and money, so the desk feels like a campus shop rather than a SaaS panel. Atkinson Hyperlegible for everything you read closely: notes, log lines, reasons. Monospace only for real MCP tool names and SKUs.
- **Motion is used only where something changed:** the active badge's pulse, the till counting down, and the run spinner. All of it turns off under `prefers-reduced-motion`.
- **Plain language throughout:** "Waiting on you", "Needs your sign-off", "Send the team to 101", "Floor is quiet", with the exact tool names kept alongside for auditing.
