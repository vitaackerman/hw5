import { useEffect, useState } from "react";
import { API_BASE } from "./api";
import { LiveFloor } from "./components/LiveFloor";
import { ShiftReport } from "./components/ShiftReport";
import { SignOffTray } from "./components/SignOffTray";
import { TicketFile } from "./components/TicketFile";
import { TicketRail } from "./components/TicketRail";
import { Till } from "./components/Till";
import { useDesk } from "./useDesk";

export default function App() {
  const desk = useDesk();
  const [selected, setSelected] = useState<number | null>(null);
  const tickets = desk.tickets?.tickets ?? [];
  const runningTicket = desk.running ? desk.run?.ticket_id ?? null : null;

  // Default to the ticket the team is working, else the first one.
  useEffect(() => {
    if (selected === null && tickets.length) setSelected(runningTicket ?? tickets[0].id);
  }, [tickets, selected, runningTicket]);

  const ticket = tickets.find((t) => t.id === selected) ?? null;

  function select(id: number) {
    setSelected(id);
    const t = tickets.find((x) => x.id === id);
    // Show that ticket's last run on the floor when nothing is running.
    if (!desk.running && t?.last_run_id && t.last_run_id !== desk.run?.run_id) void desk.viewRun(t.last_run_id);
  }

  const resolvedCount = tickets.filter((t) => t.status === "resolved").length;

  return (
    <div className="desk">
      <header className="top">
        <div className="top__brand">
          <span className="top__mark" aria-hidden="true">CC</span>
          <div>
            <h1>Campus Customs ops desk</h1>
            <p>Chapel Street shop, manager's view</p>
          </div>
        </div>
        <div className="top__facts">
          <div className="top__fact">
            <span>Desk date</span>
            <b>{desk.tickets?.today ?? "…"}</b>
          </div>
          <div className="top__fact">
            <span>Resolved</span>
            <b>{resolvedCount} of {tickets.length || 3}</b>
          </div>
          <div className={`top__fact top__conn ${desk.online ? "" : "is-down"}`}>
            <span>Desk API</span>
            <b>{desk.online ? "Connected" : "Offline"}</b>
          </div>
        </div>
      </header>

      {desk.error && (
        <div className="alert" role="alert">
          <p>{desk.error}</p>
          <button type="button" className="btn btn--ghost" onClick={desk.clearError}>Dismiss</button>
        </div>
      )}
      {!desk.online && (
        <p className="offline-help">
          Start the backend from <code>HW5/backend</code> with <code>uvicorn main:app --reload --port 8000</code>. This page is looking for it at {API_BASE}.
        </p>
      )}

      <div className="layout">
        <aside className="money">
          <Till cash={desk.cash} />
          <SignOffTray pending={desk.pending} onApprove={desk.approve} onReject={desk.reject} />
        </aside>

        <main className="work">
          <TicketRail tickets={tickets} selected={selected} runningTicket={runningTicket} onSelect={select} />
          {ticket && (
            <TicketFile
              ticket={ticket}
              teamBusy={desk.running}
              runningHere={runningTicket === ticket.id}
              starting={desk.starting}
              refreshKey={`${ticket.status}-${ticket.notes.length}-${ticket.draft_ids.length}-${ticket.pending_payment_requests.length}`}
              onDispatch={() => desk.startRun(ticket.id)}
            />
          )}
          <LiveFloor run={desk.run} events={desk.events} starting={desk.starting} />
          <ShiftReport run={desk.run} events={desk.events} />
        </main>
      </div>
    </div>
  );
}
