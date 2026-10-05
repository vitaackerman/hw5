import { useEffect, useState } from "react";
import type { PaymentRequest } from "../api";
import { money } from "../staff";
import { Badge } from "./Badge";

interface Props {
  pending: PaymentRequest[];
  onApprove: (id: string, name: string) => Promise<unknown>;
  onReject: (id: string, name: string, reason: string) => Promise<unknown>;
}

const NAME_KEY = "campus-customs-approver";

// The only place money moves: a human signs and stamps each payment request.
export function SignOffTray({ pending, onApprove, onReject }: Props) {
  const [name, setName] = useState(() => localStorage.getItem(NAME_KEY) ?? "");
  const [busy, setBusy] = useState<string | null>(null);
  const [rejecting, setRejecting] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [message, setMessage] = useState<{ tone: "ok" | "error"; text: string } | null>(null);

  useEffect(() => {
    localStorage.setItem(NAME_KEY, name);
  }, [name]);

  const signed = name.trim().length > 0;

  async function approve(r: PaymentRequest) {
    setBusy(r.id);
    setMessage(null);
    try {
      await onApprove(r.id, name.trim());
      setMessage({ tone: "ok", text: `${r.id} approved. ${money(r.amount)} paid from checking.` });
    } catch (e) {
      setMessage({ tone: "error", text: (e as Error).message });
    } finally {
      setBusy(null);
    }
  }

  async function reject(r: PaymentRequest) {
    setBusy(r.id);
    setMessage(null);
    try {
      await onReject(r.id, name.trim(), reason.trim());
      setMessage({ tone: "ok", text: `${r.id} rejected. Nothing was paid.` });
      setRejecting(null);
      setReason("");
    } catch (e) {
      setMessage({ tone: "error", text: (e as Error).message });
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="tray" aria-labelledby="tray-title">
      <header className="tray__head">
        <h2 id="tray-title">Needs your sign-off</h2>
        <span className="tray__count" aria-label={`${pending.length} waiting`}>{pending.length}</span>
      </header>
      <p className="tray__intro">The team can only ask. Cash and payment records change when you approve here.</p>

      <label className="tray__sig">
        <span>Signing as</span>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Your name" autoComplete="name" />
      </label>

      {pending.length === 0 ? (
        <p className="tray__empty">Nothing to sign. Payments the team requests will land here.</p>
      ) : (
        <ul className="slips">
          {pending.map((r) => (
            <li key={r.id} className="slip">
              <div className="slip__top">
                <span className="slip__what">{r.kind === "invoice" ? `Vendor invoice ${r.ref_id}` : `Rent for lease ${r.ref_id}`}</span>
                <span className="slip__amount">{money(r.amount)}</span>
              </div>
              <p className="slip__reason">{r.reason}</p>
              <p className="slip__meta">
                <span>{r.id}</span>
                <span>due {r.due}</span>
                {r.ticket_id && <span>ticket {r.ticket_id}</span>}
                <Badge agent={r.requested_by as never} size="chip" />
              </p>
              {rejecting === r.id ? (
                <div className="slip__reject">
                  <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Reason for rejecting" aria-label="Reason for rejecting" />
                  <button type="button" className="btn btn--ghost" onClick={() => setRejecting(null)} disabled={busy === r.id}>Keep</button>
                  <button type="button" className="btn btn--danger" onClick={() => reject(r)} disabled={!signed || !reason.trim() || busy === r.id}>
                    Reject
                  </button>
                </div>
              ) : (
                <div className="slip__actions">
                  <button type="button" className="btn btn--ghost" onClick={() => setRejecting(r.id)} disabled={busy !== null}>
                    Reject…
                  </button>
                  <button type="button" className="stamp-btn" onClick={() => approve(r)} disabled={!signed || busy !== null}>
                    {busy === r.id ? "Paying…" : `Approve & pay ${money(r.amount)}`}
                  </button>
                </div>
              )}
              {!signed && <p className="slip__hint">Type your name above to sign.</p>}
            </li>
          ))}
        </ul>
      )}
      {message && <p className={`tray__msg tray__msg--${message.tone}`} role="status">{message.text}</p>}
    </section>
  );
}
