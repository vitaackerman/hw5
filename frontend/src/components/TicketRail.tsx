import type { Ticket } from "../api";
import { STATUS_LABEL, TYPE_LABEL } from "../staff";

interface Props {
  tickets: Ticket[];
  selected: number | null;
  runningTicket: number | null;
  onSelect: (id: number) => void;
}

function itemLine(t: Ticket) {
  if (t.sku) return `${t.sku}, size ${t.size}, qty ${t.qty}`;
  if (t.lease_id) return `Lease ${t.lease_id}`;
  return null;
}

// Order slips clipped to the rail. Status comes straight from the tickets table.
export function TicketRail({ tickets, selected, runningTicket, onSelect }: Props) {
  return (
    <section className="rail" aria-labelledby="rail-title">
      <h2 id="rail-title" className="section-title">Ticket rail</h2>
      <div className="rail__bar" aria-hidden="true" />
      <div className="rail__slips" role="listbox" aria-label="Desk tickets" aria-activedescendant={selected ? `ticket-${selected}` : undefined}>
        {tickets.map((t) => {
          const waiting = t.pending_payment_requests.length > 0;
          return (
            <button
              key={t.id}
              id={`ticket-${t.id}`}
              role="option"
              aria-selected={selected === t.id}
              className={`order status-${t.status} ${selected === t.id ? "is-selected" : ""} ${runningTicket === t.id ? "is-running" : ""}`}
              onClick={() => onSelect(t.id)}
            >
              <span className="order__clip" aria-hidden="true" />
              <span className="order__no">{t.id}</span>
              <span className="order__type">{TYPE_LABEL[t.type] ?? t.type}</span>
              <span className="order__subject">{t.subject}</span>
              <span className="order__from">{t.requester}</span>
              {itemLine(t) && <span className="order__item">{itemLine(t)}</span>}
              <span className="order__foot">
                <span className={`state state--${t.status}`}>{STATUS_LABEL[t.status] ?? t.status}</span>
                {runningTicket === t.id && <span className="order__live">Team on it</span>}
                {waiting && runningTicket !== t.id && (
                  <span className="order__flag">{t.pending_payment_requests.length} to sign</span>
                )}
              </span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
