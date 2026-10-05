import type { CSSProperties } from "react";
import type { AgentEvent, RunInfo } from "../api";
import { shiftReport } from "../feed";
import { STAFF, STATUS_LABEL } from "../staff";
import { Badge } from "./Badge";

// After a run: the boss's call on top, then one line of work per specialist.
export function ShiftReport({ run, events }: { run: RunInfo | null; events: AgentEvent[] }) {
  if (!run || run.status === "running") return null;
  if (run.status === "failed") {
    return (
      <section className="report report--failed" aria-labelledby="report-title">
        <h2 id="report-title" className="section-title">Shift report</h2>
        <p>The run on ticket {run.ticket_id} stopped early: {run.error}</p>
        <p>Nothing that needs your approval was paid. Check the log above for the last step the team finished.</p>
      </section>
    );
  }
  const shifts = shiftReport(events).filter((s) => s.agent !== "boss");
  const boss = run.output;

  return (
    <section className="report" aria-labelledby="report-title">
      <h2 id="report-title" className="section-title">Shift report, ticket {run.ticket_id}</h2>

      {boss && (
        <article className="report__boss">
          <Badge agent="boss" size="chip" />
          <p className="report__summary">{boss.summary}</p>
          {boss.decisions.map((d) => (
            <div key={d.ticket_id} className="decision">
              <p>
                <b>Ticket {d.ticket_id}</b>, now <span className={`state state--${d.status_after}`}>{STATUS_LABEL[d.status_after] ?? d.status_after}</span>
              </p>
              <p>{d.decision}</p>
              {d.waiting_on.length > 0 && <p className="decision__wait">Waiting on: {d.waiting_on.join("; ")}</p>}
            </div>
          ))}
          {boss.human_actions_needed.length > 0 && (
            <div className="report__todo">
              <h3>For you</h3>
              <ul>{boss.human_actions_needed.map((h, i) => <li key={i}>{h}</li>)}</ul>
            </div>
          )}
        </article>
      )}

      <div className="report__team">
        {shifts.length === 0 && <p className="report__none">The boss handled this one without calling a specialist.</p>}
        {shifts.map((s, i) => (
          <article key={i} className="shift" style={{ "--dept": STAFF[s.agent].color } as CSSProperties}>
            <Badge agent={s.agent} size="chip" />
            <p>{s.report.summary}</p>
            {s.report.actions_taken && s.report.actions_taken.length > 0 && (
              <p className="shift__did"><b>Did:</b> {s.report.actions_taken.join("; ")}</p>
            )}
            {s.report.blocked_by && s.report.blocked_by.length > 0 && (
              <p className="shift__blocked"><b>Blocked by:</b> {s.report.blocked_by.join("; ")}</p>
            )}
            {s.report.needs_human_approval && s.report.needs_human_approval.length > 0 && (
              <p className="shift__sign"><b>Needs you:</b> {s.report.needs_human_approval.join("; ")}</p>
            )}
            {s.tools.length > 0 && (
              <p className="shift__tools">{s.tools.map((t) => <code key={t}>{t}</code>)}</p>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}
