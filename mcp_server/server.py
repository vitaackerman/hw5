"""Campus Customs MCP server: the only way the agents read or change shop data.

Database: data/campus_customs_new.db (the working copy). The original
data/campus_customs.db is never opened; the server refuses to start on it.
Read tools open SQLite in read-only mode. Write tools enforce the shop rules
in code, so a misbehaving agent can't skip them.

Drafts and payment requests are not shop records, so they live in JSON files
under output/ (drafts.json, payment_requests.json), never in the database.
A payment request changes nothing until a human runs approve_payment.

Run (stdio): python mcp_server/server.py
Tests may point CAMPUS_CUSTOMS_DB / CAMPUS_CUSTOMS_STATE_DIR at scratch copies.
"""

from __future__ import annotations

import calendar
import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Literal

from fastmcp import FastMCP

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
DB_PATH = Path(os.getenv("CAMPUS_CUSTOMS_DB", PROJECT / "data" / "campus_customs_new.db")).resolve()
STATE_DIR = Path(os.getenv("CAMPUS_CUSTOMS_STATE_DIR", PROJECT / "output")).resolve()
DRAFTS_PATH = STATE_DIR / "drafts.json"
REQUESTS_PATH = STATE_DIR / "payment_requests.json"

if DB_PATH.name == "campus_customs.db":
    raise SystemExit("Refusing to use the original data/campus_customs.db. Use campus_customs_new.db.")

# Names the agents use; human-only tools reject these as approvers.
AGENT_NAMES = {"boss", "inventory", "accounting", "facilities", "customer_service", "customer service"}
TICKET_STATUSES = ("open", "in_progress", "waiting_on_approval", "resolved")

mcp = FastMCP("campus-customs")
_state_lock = threading.Lock()


# ---------- helpers ----------

def _connect(write: bool = False) -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Working database not found at {DB_PATH}. "
            "Copy data/campus_customs.db to data/campus_customs_new.db first."
        )
    mode = "rw" if write else "ro"
    conn = sqlite3.connect(f"{DB_PATH.as_uri()}?mode={mode}", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def _transaction() -> Iterator[sqlite3.Connection]:
    """One write transaction: commits on success, rolls back on any error."""
    conn = _connect(write=True)
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def _rows(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, params)]


def _one(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> dict[str, Any] | None:
    row = conn.execute(sql, params).fetchone()
    return dict(row) if row else None


def _today(conn: sqlite3.Connection) -> str | None:
    row = conn.execute("SELECT date_today FROM desk LIMIT 1").fetchone()
    return row["date_today"] if row else None


def _days_until(due: str, today: str | None) -> int | None:
    if today is None:
        return None
    return (date.fromisoformat(due) - date.fromisoformat(today)).days


def _add_month(iso_day: str) -> str:
    d = date.fromisoformat(iso_day)
    year, month = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    return d.replace(year=year, month=month, day=min(d.day, calendar.monthrange(year, month)[1])).isoformat()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _fail(message: str, **details: Any) -> dict[str, Any]:
    """Rule refusals are normal results, so the agent sees why and can report it."""
    return {"ok": False, "error": message, **details}


def _load(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8") or "[]")


def _save(path: Path, items: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(items, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _append_ticket_note(conn: sqlite3.Connection, ticket_id: int, today: str | None, who: str, note: str) -> None:
    line = f"[{today}] {who}: {note.strip()}"
    conn.execute(
        "UPDATE tickets SET notes = CASE WHEN notes IS NULL OR notes = '' THEN ? ELSE notes || char(10) || ? END WHERE id = ?",
        (line, line, ticket_id),
    )


def _unpaid_invoices_for(conn: sqlite3.Connection, sku: str, invoice_id: int | None) -> list[dict[str, Any]]:
    """Unpaid invoices tied to a product: linked from the ticket, or naming the SKU."""
    return _rows(
        conn,
        "SELECT id, amount, due_date, status, description FROM invoices "
        "WHERE status != 'paid' AND (id = ? OR description LIKE ?)",
        (invoice_id if invoice_id is not None else -1, f"%{sku}%"),
    )


# ---------- read tools ----------

@mcp.tool
def list_open_tickets() -> dict[str, Any]:
    """List every ticket that is not resolved, with the shop's current date.

    "today" is desk.date_today, which is the date all agents must use.
    Reads: desk, tickets.
    """
    with _connect() as conn:
        desk = _one(conn, "SELECT date_today, notes FROM desk LIMIT 1")
        tickets = _rows(
            conn,
            "SELECT id, type, requester, subject, sku, size, qty, lease_id, invoice_id, status, created_at "
            "FROM tickets WHERE status != 'resolved' ORDER BY id",
        )
    return {"today": desk["date_today"] if desk else None, "desk_notes": desk["notes"] if desk else None, "tickets": tickets}


@mcp.tool
def get_ticket(ticket_id: int) -> dict[str, Any]:
    """Get one ticket with everything linked to it, for investigating or rechecking.

    Includes the linked lease and invoice (with vendor and recorded payments),
    plus this ticket's payment requests and drafts.
    Reads: desk, tickets, leases, invoices, vendors, payments (+ payment_requests.json, drafts.json).
    """
    with _connect() as conn:
        today = _today(conn)
        ticket = _one(conn, "SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        if not ticket:
            return _fail(f"No ticket with id {ticket_id}.")
        lease = invoice = None
        if ticket["lease_id"] is not None:
            lease = _one(conn, "SELECT * FROM leases WHERE id = ?", (ticket["lease_id"],))
            if lease:
                lease["days_until_due"] = _days_until(lease["next_due"], today)
                lease["payments"] = _rows(
                    conn, "SELECT * FROM payments WHERE kind = 'lease' AND ref_id = ? ORDER BY id", (lease["id"],)
                )
        if ticket["invoice_id"] is not None:
            invoice = _one(
                conn,
                "SELECT i.*, v.name AS vendor_name, v.specialty AS vendor_specialty, v.lead_days AS vendor_lead_days "
                "FROM invoices i JOIN vendors v ON v.id = i.vendor_id WHERE i.id = ?",
                (ticket["invoice_id"],),
            )
            if invoice:
                invoice["days_until_due"] = _days_until(invoice["due_date"], today)
                invoice["payments"] = _rows(
                    conn, "SELECT * FROM payments WHERE kind = 'invoice' AND ref_id = ? ORDER BY id", (invoice["id"],)
                )
    with _state_lock:
        requests = [r for r in _load(REQUESTS_PATH) if r.get("ticket_id") == ticket_id]
        drafts = [d for d in _load(DRAFTS_PATH) if d.get("ticket_id") == ticket_id]
    return {
        "ok": True,
        "today": today,
        "ticket": ticket,
        "lease": lease,
        "invoice": invoice,
        "payment_requests": requests,
        "drafts": drafts,
    }


@mcp.tool
def check_stock(sku: str, size: str) -> dict[str, Any]:
    """Check stock for one SKU and size, plus restock information.

    Returns the inventory row for that size, the stock in every other size of
    the same SKU, invoices connected to restocking this SKU (linked from a
    ticket or naming the SKU in their description), and the vendor list with
    lead times. Reads: inventory, tickets, invoices, vendors, desk.
    """
    sku, size = sku.strip().upper(), size.strip().upper()
    with _connect() as conn:
        today = _today(conn)
        item = _rows(
            conn,
            "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ? AND size = ?",
            (sku, size),
        )
        all_sizes = _rows(
            conn,
            "SELECT size, qty, location FROM inventory WHERE sku = ? ORDER BY rowid",
            (sku,),
        )
        invoices = _rows(
            conn,
            """
            SELECT DISTINCT i.id, i.amount, i.due_date, i.status, i.description,
                   v.id AS vendor_id, v.name AS vendor_name, v.lead_days
            FROM invoices i
            JOIN vendors v ON v.id = i.vendor_id
            LEFT JOIN tickets t ON t.invoice_id = i.id
            WHERE (t.sku = ? AND t.size = ?) OR i.description LIKE ?
            ORDER BY i.due_date
            """,
            (sku, size, f"%{sku}%"),
        )
        vendors = _rows(conn, "SELECT id, name, specialty, lead_days FROM vendors ORDER BY id")

    for inv in invoices:
        inv["days_until_due"] = _days_until(inv["due_date"], today)

    if not item:
        return {
            "as_of": today,
            "found": False,
            "sku": sku,
            "size": size,
            "message": "No inventory row for this SKU and size.",
            "sizes_on_record_for_sku": all_sizes,
        }

    return {
        "as_of": today,
        "found": True,
        "item": item[0],
        "in_stock": item[0]["qty"] > 0,
        "all_sizes": all_sizes,
        "restock_invoices": invoices,
        "vendors": vendors,
    }


@mcp.tool
def list_vendors() -> dict[str, Any]:
    """List vendors with their specialty and lead time in days. Reads: vendors."""
    with _connect() as conn:
        return {"vendors": _rows(conn, "SELECT id, name, specialty, lead_days FROM vendors ORDER BY id")}


@mcp.tool
def get_cash_and_obligations() -> dict[str, Any]:
    """Show cash on hand and what the shop owes: unpaid invoices and lease rent.

    Days until due are counted from the shop's desk date (negative = overdue).
    Also lists payments already recorded and payment requests still waiting
    for human approval (those have NOT reduced cash). Reads: desk,
    cash_accounts, invoices, vendors, leases, payments (+ payment_requests.json).
    """
    with _connect() as conn:
        today = _today(conn)
        accounts = _rows(conn, "SELECT name, balance, date FROM cash_accounts ORDER BY name")
        invoices = _rows(
            conn,
            """
            SELECT i.id, i.amount, i.due_date, i.status, i.description,
                   v.name AS vendor_name
            FROM invoices i
            JOIN vendors v ON v.id = i.vendor_id
            WHERE i.status != 'paid'
            ORDER BY i.due_date
            """,
        )
        leases = _rows(
            conn,
            "SELECT id, space_name, landlord, monthly_rent, next_due, notes FROM leases ORDER BY next_due",
        )
        payments = _rows(
            conn,
            "SELECT id, kind, ref_id, amount, account, paid_at, approved_by FROM payments ORDER BY paid_at",
        )
    with _state_lock:
        pending = [r for r in _load(REQUESTS_PATH) if r["status"] == "pending_human_approval"]

    for inv in invoices:
        inv["days_until_due"] = _days_until(inv["due_date"], today)
    for lease in leases:
        lease["days_until_due"] = _days_until(lease["next_due"], today)

    total_cash = round(sum(a["balance"] for a in accounts), 2)
    total_due = round(
        sum(i["amount"] for i in invoices) + sum(l["monthly_rent"] for l in leases), 2
    )
    return {
        "as_of": today,
        "cash_accounts": accounts,
        "total_cash": total_cash,
        "unpaid_invoices": invoices,
        "lease_rent_due": leases,
        "total_obligations": total_due,
        "cash_after_all_obligations": round(total_cash - total_due, 2),
        "payments_recorded": payments,
        "pending_payment_requests": pending,
    }


@mcp.tool
def get_pricing(sku: str, qty: int = 1, discount_pct: float = 0) -> dict[str, Any]:
    """Show cost, list price, and margin for a SKU, with totals for a quantity.

    margin_pct_of_list is also the deepest discount off list that still covers
    unit cost. Pass discount_pct (e.g. 15 for 15% off) to see the discounted
    price and whether it stays above cost. Includes current stock by size so a
    bulk request can be checked against inventory. Reads: pricing, inventory.
    """
    sku = sku.strip().upper()
    if qty < 1:
        return {"sku": sku, "found": False, "message": "qty must be at least 1."}
    if not 0 <= discount_pct < 100:
        return {"sku": sku, "found": False, "message": "discount_pct must be from 0 up to (not including) 100."}
    with _connect() as conn:
        price = _rows(conn, "SELECT sku, unit_cost, list_price FROM pricing WHERE sku = ?", (sku,))
        stock = _rows(
            conn,
            "SELECT name, size, qty FROM inventory WHERE sku = ? ORDER BY rowid",
            (sku,),
        )

    if not price:
        return {"sku": sku, "found": False, "message": "No pricing row for this SKU."}

    cost, list_price = price[0]["unit_cost"], price[0]["list_price"]
    unit_margin = list_price - cost
    result = {
        "found": True,
        "sku": sku,
        "name": stock[0]["name"] if stock else None,
        "unit_cost": cost,
        "list_price": list_price,
        "unit_margin": round(unit_margin, 2),
        "margin_pct_of_list": round(unit_margin / list_price * 100, 1) if list_price else None,
        "qty": qty,
        "total_cost": round(cost * qty, 2),
        "total_at_list": round(list_price * qty, 2),
        "total_margin_at_list": round(unit_margin * qty, 2),
        "stock_by_size": [{"size": s["size"], "qty": s["qty"]} for s in stock],
    }
    if discount_pct:
        unit_price = round(list_price * (1 - discount_pct / 100), 2)
        result["discount"] = {
            "discount_pct": discount_pct,
            "unit_price": unit_price,
            "unit_margin": round(unit_price - cost, 2),
            "total_price": round(unit_price * qty, 2),
            "total_margin": round((unit_price - cost) * qty, 2),
            "above_cost": unit_price > cost,
        }
    return result


# ---------- agent write tools ----------

@mcp.tool
def create_draft(
    kind: Literal["customer_email", "vendor_message", "landlord_message"],
    to: str,
    subject: str,
    body: str,
    created_by: str,
    ticket_id: int | None = None,
) -> dict[str, Any]:
    """Save a message draft for a human to review. Nothing is ever sent.

    Use for customer emails, vendor messages (instead of calling vendors), and
    landlord messages. Writes: output/drafts.json only (no database change).
    """
    if not (to.strip() and subject.strip() and body.strip() and created_by.strip()):
        return _fail("to, subject, body and created_by are all required.")
    with _state_lock:
        drafts = _load(DRAFTS_PATH)
        draft = {
            "id": f"D-{len(drafts) + 1}",
            "kind": kind,
            "ticket_id": ticket_id,
            "to": to.strip(),
            "subject": subject.strip(),
            "body": body.strip(),
            "created_by": created_by.strip(),
            "created_at": _now(),
            "status": "draft_not_sent",
        }
        drafts.append(draft)
        _save(DRAFTS_PATH, drafts)
    return {"ok": True, "draft": draft, "note": "Saved as a draft only. Nothing was sent."}


@mcp.tool
def request_payment(
    kind: Literal["invoice", "lease"],
    ref_id: int,
    amount: float,
    reason: str,
    requested_by: str,
    ticket_id: int | None = None,
    account: str = "checking",
) -> dict[str, Any]:
    """Ask a human to approve paying an invoice or a lease's rent.

    Checks the amount matches the invoice/rent, the bill is still unpaid, there
    is no duplicate pending request, and the account can cover it after other
    pending requests. Does NOT reduce cash, record a payment, or mark anything
    paid; that only happens when a human approves. Reads: desk, cash_accounts,
    invoices, leases. Writes: output/payment_requests.json only.
    """
    if not reason.strip() or not requested_by.strip():
        return _fail("reason and requested_by are required.")
    with _connect() as conn:
        today = _today(conn)
        acct = _one(conn, "SELECT name, balance FROM cash_accounts WHERE name = ?", (account,))
        if not acct:
            return _fail(f"No cash account named {account!r}.")
        if kind == "invoice":
            bill = _one(conn, "SELECT id, amount, status, due_date FROM invoices WHERE id = ?", (ref_id,))
            if not bill:
                return _fail(f"No invoice with id {ref_id}.")
            if bill["status"] == "paid":
                return _fail(f"Invoice {ref_id} is already paid.")
            expected, due = bill["amount"], bill["due_date"]
        else:
            bill = _one(conn, "SELECT id, monthly_rent, next_due FROM leases WHERE id = ?", (ref_id,))
            if not bill:
                return _fail(f"No lease with id {ref_id}.")
            expected, due = bill["monthly_rent"], bill["next_due"]
    if round(amount, 2) != round(expected, 2):
        return _fail(f"Amount {amount} does not match the {kind} amount {expected}.", expected_amount=expected)

    with _state_lock:
        requests = _load(REQUESTS_PATH)
        pending = [r for r in requests if r["status"] == "pending_human_approval"]
        if any(r["kind"] == kind and r["ref_id"] == ref_id for r in pending):
            return _fail(f"A pending request to pay {kind} {ref_id} already exists.")
        committed = sum(r["amount"] for r in pending if r["account"] == account)
        available = round(acct["balance"] - committed, 2)
        if amount > available:
            return _fail(
                "Not enough cash once other pending requests are counted.",
                balance=acct["balance"], already_requested=committed, available=available,
            )
        request = {
            "id": f"PR-{len(requests) + 1}",
            "kind": kind,
            "ref_id": ref_id,
            "amount": round(amount, 2),
            "account": account,
            "due": due,
            "ticket_id": ticket_id,
            "reason": reason.strip(),
            "requested_by": requested_by.strip(),
            "requested_on": today,
            "requested_at": _now(),
            "status": "pending_human_approval",
        }
        requests.append(request)
        _save(REQUESTS_PATH, requests)
    return {
        "ok": True,
        "request": request,
        "note": "Waiting for human approval. Cash, payments and the bill are unchanged.",
        "cash_available_after_pending": round(available - amount, 2),
    }


@mcp.tool
def ship_order(ticket_id: int, shipped_by: str) -> dict[str, Any]:
    """Ship a customer_order ticket: subtract its qty from inventory.

    Refuses if the ticket isn't an open customer order, if stock is short, or
    if any invoice for that product is still unpaid. Does not resolve the
    ticket. Reads: tickets, invoices, inventory. Writes: inventory.qty, tickets.notes.
    """
    if not shipped_by.strip():
        return _fail("shipped_by is required.")
    with _transaction() as conn:
        today = _today(conn)
        t = _one(conn, "SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        if not t:
            return _fail(f"No ticket with id {ticket_id}.")
        if t["type"] != "customer_order" or t["status"] == "resolved":
            return _fail("Only unresolved customer_order tickets can be shipped.", type=t["type"], status=t["status"])
        if not (t["sku"] and t["size"] and t["qty"]):
            return _fail("Ticket is missing sku, size or qty.")
        if "SHIPPED" in (t["notes"] or ""):
            return _fail("This ticket's order was already shipped.")
        unpaid = _unpaid_invoices_for(conn, t["sku"], t["invoice_id"])
        if unpaid:
            return _fail("Can't ship while an invoice for this product is unpaid.", unpaid_invoices=unpaid)
        row = _one(conn, "SELECT qty FROM inventory WHERE sku = ? AND size = ?", (t["sku"], t["size"]))
        if not row:
            return _fail("No inventory row for this SKU and size.")
        if row["qty"] < t["qty"]:
            return _fail("Not enough stock to ship.", in_stock=row["qty"], needed=t["qty"])
        conn.execute(
            "UPDATE inventory SET qty = qty - ? WHERE sku = ? AND size = ?", (t["qty"], t["sku"], t["size"])
        )
        _append_ticket_note(conn, ticket_id, today, shipped_by, f"SHIPPED {t['qty']} x {t['sku']} {t['size']}")
        after = conn.execute(
            "SELECT qty FROM inventory WHERE sku = ? AND size = ?", (t["sku"], t["size"])
        ).fetchone()["qty"]
    return {"ok": True, "ticket_id": ticket_id, "shipped": t["qty"], "sku": t["sku"], "size": t["size"], "qty_left": after}


@mcp.tool
def update_ticket(
    ticket_id: int,
    status: Literal["open", "in_progress", "waiting_on_approval", "resolved"],
    note: str,
    updated_by: str,
) -> dict[str, Any]:
    """Change a ticket's status and append a dated note.

    Resolving is refused while the ticket still has a payment request waiting
    for human approval. Recheck the database (get_ticket etc.) before resolving.
    Reads/writes: tickets.
    """
    if not note.strip() or not updated_by.strip():
        return _fail("note and updated_by are required.")
    if status == "resolved":
        with _state_lock:
            waiting = [
                r["id"] for r in _load(REQUESTS_PATH)
                if r.get("ticket_id") == ticket_id and r["status"] == "pending_human_approval"
            ]
        if waiting:
            return _fail("Can't resolve: payment requests still need human approval.", pending_requests=waiting)
    with _transaction() as conn:
        today = _today(conn)
        if not _one(conn, "SELECT id FROM tickets WHERE id = ?", (ticket_id,)):
            return _fail(f"No ticket with id {ticket_id}.")
        conn.execute("UPDATE tickets SET status = ? WHERE id = ?", (status, ticket_id))
        _append_ticket_note(conn, ticket_id, today, updated_by, note)
        ticket = _one(conn, "SELECT id, status, notes FROM tickets WHERE id = ?", (ticket_id,))
    return {"ok": True, "ticket": ticket}


# ---------- human-only tools (never given to agents) ----------

def _human(name: str) -> str | None:
    name = name.strip()
    if not name or name.lower() in AGENT_NAMES:
        return None
    return name


@mcp.tool(tags={"human_only"})
def approve_payment(request_id: str, approved_by: str) -> dict[str, Any]:
    """HUMAN ONLY. Approve a pending payment request and make the payment.

    In one transaction: rechecks the bill and cash, inserts the payments row,
    reduces the cash balance, and marks the invoice paid or moves the lease's
    next_due forward one month. Reads/writes: desk, cash_accounts, payments,
    invoices, leases (+ payment_requests.json).
    """
    approver = _human(approved_by)
    if not approver:
        return _fail("approved_by must be a human's name, not an agent.")
    with _state_lock:
        requests = _load(REQUESTS_PATH)
        req = next((r for r in requests if r["id"] == request_id), None)
        if not req:
            return _fail(f"No payment request {request_id}.")
        if req["status"] != "pending_human_approval":
            return _fail(f"Request {request_id} is already {req['status']}.")
        with _transaction() as conn:
            today = _today(conn)
            acct = _one(conn, "SELECT balance FROM cash_accounts WHERE name = ?", (req["account"],))
            if not acct or acct["balance"] < req["amount"]:
                return _fail("Not enough cash in the account.", balance=acct and acct["balance"])
            if req["kind"] == "invoice":
                inv = _one(conn, "SELECT status FROM invoices WHERE id = ?", (req["ref_id"],))
                if not inv or inv["status"] == "paid":
                    return _fail("Invoice is missing or already paid.")
                conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (req["ref_id"],))
            else:
                lease = _one(conn, "SELECT next_due FROM leases WHERE id = ?", (req["ref_id"],))
                if not lease or lease["next_due"] != req["due"]:
                    return _fail("Lease is missing or that rent period was already paid.")
                conn.execute(
                    "UPDATE leases SET next_due = ? WHERE id = ?", (_add_month(lease["next_due"]), req["ref_id"])
                )
            cur = conn.execute(
                "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) VALUES (?, ?, ?, ?, ?, ?)",
                (req["kind"], req["ref_id"], req["amount"], req["account"], today, approver),
            )
            payment_id = cur.lastrowid
            conn.execute(
                "UPDATE cash_accounts SET balance = balance - ?, date = ? WHERE name = ?",
                (req["amount"], today, req["account"]),
            )
            balance = conn.execute(
                "SELECT balance FROM cash_accounts WHERE name = ?", (req["account"],)
            ).fetchone()["balance"]
        req.update(status="approved", decided_by=approver, decided_at=_now(), payment_id=payment_id)
        _save(REQUESTS_PATH, requests)
    return {"ok": True, "request": req, "payment_id": payment_id, "new_balance": balance}


@mcp.tool(tags={"human_only"})
def reject_payment(request_id: str, rejected_by: str, reason: str) -> dict[str, Any]:
    """HUMAN ONLY. Reject a pending payment request. Nothing in the database changes.

    Writes: output/payment_requests.json only.
    """
    rejecter = _human(rejected_by)
    if not rejecter:
        return _fail("rejected_by must be a human's name, not an agent.")
    with _state_lock:
        requests = _load(REQUESTS_PATH)
        req = next((r for r in requests if r["id"] == request_id), None)
        if not req:
            return _fail(f"No payment request {request_id}.")
        if req["status"] != "pending_human_approval":
            return _fail(f"Request {request_id} is already {req['status']}.")
        req.update(status="rejected", decided_by=rejecter, decided_at=_now(), reject_reason=reason.strip())
        _save(REQUESTS_PATH, requests)
    return {"ok": True, "request": req}


if __name__ == "__main__":
    mcp.run(show_banner=False)
