import { useEffect, useState } from "react";
import { api, type Ticket, type TicketDetail } from "../api";
import { STATUS_LABEL, TYPE_LABEL } from "../staff";

interface Props {
  ticket: Ticket;
  teamBusy: boolean;
  runningHere: boolean;
  starting: boolean;
  refreshKey: string;
  onDispatch: () => void;
}

// The open ticket: what the database says about it, what the team left behind, and the dispatch button.
export function TicketFile({ ticket, teamBusy, runningHere, starting, refreshKey, onDispatch }: Props) {
  const [detail, setDetail] = useState<TicketDetail | null>(null);
  const [openDraft, setOpenDraft] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    api.ticket(ticket.id).then((d) => live && setDetail(d)).catch(() => live && setDetail(null));
    return () => {
      live = false;
    };
  }, [ticket.id, refreshKey]);

  const resolved = ticket.status === "resolved";
  const disabled = resolved || teamBusy || starting;
  const label = runningHere
    ? "Team is working this ticket"
    : starting
      ? "Dispatching…"
      : teamBusy
        ? "Team is busy on another ticket"
        : resolved
          ? "Resolved, nothing to dispatch"
          : ticket.last_run_id
            ? `Send the team back to ${ticket.id}`
            : `Send the team to ${ticket.id}`;

  const invoice = detail?.invoice as { id: number; amount: number; status: string; due_date: string; vendor_name: string } | null;
  const lease = detail?.lease as { id: number; space_name: string; monthly_rent: number; next_due: string; landlord: string } | null;

  return (
    <section className="file" aria-labelledby="file-title">
      <div className="file__head">
        <div>
          <p className="file__kicker">{TYPE_LABEL[ticket.type] ?? ticket.type}, from {ticket.requester}</p>
          <h2 id="file-title">
            <span className="file__no">{ticket.id}</span> {ticket.subject}
          </h2>
        </div>
        <span className={`state state--${ticket.status} state--big`}>{STATUS_LABEL[ticket.status] ?? ticket.status}</span>
      </div>

      <dl className="file__facts">
        {ticket.sku && (
          <div><dt>Item</dt><dd>{ticket.sku}, size {ticket.size}, qty {ticket.qty}</dd></div>
        )}
        {invoice && (
          <div><dt>Linked invoice</dt><dd>#{invoice.id} {invoice.vendor_name}, ${invoice.amount.toFixed(2)}, {invoice.status}, due {invoice.due_date}</dd></div>
        )}
        {lease && (
          <div><dt>Linked lease</dt><dd>{lease.space_name}, ${lease.monthly_rent.toFixed(2)} to {lease.landlord}, next due {lease.next_due}</dd></div>
        )}
        <div><dt>Opened</dt><dd>{ticket.created_at.replace("T", " ").slice(0, 16)}</dd></div>
      </dl>

      <div className="file__notes">
        <h3>Notes on the ticket</h3>
        <ul>
          {ticket.notes.map((n, i) => (
            <li key={i} className={i === 0 ? "is-original" : ""}>{n}</li>
          ))}
        </ul>
      </div>

      {detail && detail.drafts.length > 0 && (
        <div className="file__drafts">
          <h3>Drafts waiting for you to send</h3>
          {detail.drafts.map((d) => (
            <div key={d.id} className="draft">
              <button type="button" className="draft__toggle" aria-expanded={openDraft === d.id} onClick={() => setOpenDraft(openDraft === d.id ? null : d.id)}>
                <span>{d.id}</span> To {d.to}: {d.subject}
                <span className="draft__unsent">Not sent</span>
              </button>
              {openDraft === d.id && <pre className="draft__body">{d.body}</pre>}
            </div>
          ))}
        </div>
      )}

      <div className="dispatch">
        <button type="button" className={`dispatch__btn ${runningHere ? "is-running" : ""}`} onClick={onDispatch} disabled={disabled} aria-busy={runningHere || starting}>
          {(runningHere || starting) && <span className="spinner" aria-hidden="true" />}
          {label}
        </button>
        <p className="dispatch__hint">
          The boss reads this ticket, decides which specialists to call, and records the outcome. Payments wait for your sign-off.
        </p>
      </div>
    </section>
  );
}
