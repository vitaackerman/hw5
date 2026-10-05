# Campus Customs MCP Server

A FastMCP server that is the **only** way the Campus Customs agents (boss, inventory, accounting, facilities, customer service) read or change shop data. The agents in `backend/` connect to it over stdio. Claude Code also connects through `.mcp.json`.

## Database and files

- Uses **only** the working copy `data/campus_customs_new.db`. The server refuses to start if pointed at the original `data/campus_customs.db`, and it never falls back to it.
- Read tools open SQLite read-only. Each write tool runs in a single transaction and checks the shop rules in code.
- Drafts and payment requests aren't shop records, so they're kept in `output/drafts.json` and `output/payment_requests.json`, not in the database.
- Tools return only values stored in the database, or arithmetic on those values. A missing SKU or ticket returns `found: false` or `ok: false` instead of a guess. Rule refusals come back as `{"ok": false, "error": ...}`.

## Tools

### Read (all agents)
| Tool | Arguments | What it does |
|------|-----------|--------------|
| `list_open_tickets` | none | Unresolved tickets, plus `today` (`desk.date_today`). |
| `get_ticket` | `ticket_id` | One ticket with its linked lease and invoice (with vendor and recorded payments), plus its payment requests and drafts. Used to investigate and to recheck before resolving. |
| `check_stock` | `sku`, `size` | Stock for that size and the item's other sizes, invoices tied to restocking the SKU, and vendors with lead days. |
| `list_vendors` | none | Vendors with specialty and `lead_days`. |
| `get_cash_and_obligations` | none | Cash balances, unpaid invoices and lease rent with days until due, totals, cash left, recorded payments, and pending payment requests. |
| `get_pricing` | `sku`, `qty` (1), `discount_pct` (0) | Cost, list price, margin and totals for `qty`, stock by size, and with a discount, the discounted price and whether it stays above cost. |

### Write (given only to the agents whose role owns them)
| Tool | Agents | What it does |
|------|--------|--------------|
| `create_draft` | inventory, accounting, facilities, customer service | Saves a customer, vendor or landlord message as a draft. **Nothing is sent.** |
| `request_payment` | accounting, facilities | Asks a human to approve paying an invoice or rent. Checks the amount matches, the bill is unpaid, there's no duplicate request, and cash covers it. **Changes no cash, payment rows or bills.** |
| `ship_order` | inventory | Subtracts a `customer_order` ticket's qty from inventory. **Refuses while any invoice for that product is unpaid**, when stock is short, or when the order was already shipped. |
| `update_ticket` | boss | Sets ticket status and appends a dated note. Refuses `resolved` while a payment request is still pending. |

### Human only (never given to agents)
| Tool | What it does |
|------|--------------|
| `approve_payment` | `request_id`, `approved_by`: rechecks the request, then in one transaction inserts the `payments` row, reduces cash, and marks the invoice paid or moves the lease's `next_due` forward a month. Agent names are rejected as approvers. |
| `reject_payment` | `request_id`, `rejected_by`, `reason`: marks the request rejected. Nothing in the database changes. |

Use `backend/approve.py` to approve or reject payments:

```bash
.venv/bin/python -m backend.approve list
```

## Setup and run

```bash
.venv/bin/python -m pip install -r requirements.txt
```

Run over stdio from the HW5 folder (the agents and Claude Code launch it automatically):

```bash
.venv/bin/python mcp_server/server.py
```

For tests only, `CAMPUS_CUSTOMS_DB` and `CAMPUS_CUSTOMS_STATE_DIR` can point the server at scratch copies.
