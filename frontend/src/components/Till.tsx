import { useEffect, useRef, useState } from "react";
import type { Cash } from "../api";
import { money } from "../staff";
import { useCountUp } from "../useCountUp";

// The register: checking balance in big digits, with a receipt tape of what's pending and what's been paid.
export function Till({ cash }: { cash: Cash | null }) {
  const shown = useCountUp(cash?.balance ?? null);
  const prev = useRef<number | null>(null);
  const [change, setChange] = useState<number | null>(null);

  useEffect(() => {
    if (!cash) return;
    if (prev.current !== null && prev.current !== cash.balance) {
      setChange(cash.balance - prev.current);
      const t = window.setTimeout(() => setChange(null), 6000);
      prev.current = cash.balance;
      return () => window.clearTimeout(t);
    }
    prev.current = cash.balance;
  }, [cash]);

  return (
    <section className="till" aria-labelledby="till-title">
      <div className="till__display">
        <h2 id="till-title" className="till__label">Checking balance</h2>
        <output className={`till__amount ${change !== null ? "is-changing" : ""}`} aria-live="polite">
          {shown === null ? "…" : money(shown)}
        </output>
        <p className="till__meta">
          <span>{cash ? <>From <code>cash_accounts</code>, updated {cash.balance_date}</> : "Loading from the desk API"}</span>
          {change !== null && <span className="till__change">{change < 0 ? "−" : "+"}{money(Math.abs(change))} just now</span>}
        </p>
      </div>

      {cash && (
        <div className="tape">
          <dl className="tape__lines">
            <div>
              <dt>Waiting for your approval</dt>
              <dd>{cash.pending_requests_total ? `−${money(cash.pending_requests_total)}` : money(0)}</dd>
            </div>
            <div className="tape__total">
              <dt>Free after approvals</dt>
              <dd>{money(cash.available_after_pending)}</dd>
            </div>
            <div>
              <dt>Unpaid vendor invoices</dt>
              <dd>{money(cash.unpaid_invoices_total)}</dd>
            </div>
            <div>
              <dt>Rent coming due</dt>
              <dd>{money(cash.rent_due_total)}</dd>
            </div>
            <div className={`tape__total ${cash.cash_after_all_obligations < 500 ? "is-tight" : ""}`}>
              <dt>Left if every bill is paid</dt>
              <dd>{money(cash.cash_after_all_obligations)}</dd>
            </div>
          </dl>
          <h3 className="tape__head">Paid out</h3>
          {cash.payments.length === 0 ? (
            <p className="tape__empty">No payments yet. Money only leaves after you approve it.</p>
          ) : (
            <ul className="tape__paid">
              {cash.payments.map((p) => (
                <li key={p.id}>
                  <span>
                    {p.kind === "invoice" ? `Invoice ${p.ref_id}` : `Rent, lease ${p.ref_id}`}
                    <small>Approved by {p.approved_by} on {p.paid_at}</small>
                  </span>
                  <b>−{money(p.amount)}</b>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}
