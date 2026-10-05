import { useEffect, useMemo, useRef } from "react";
import type { CSSProperties } from "react";
import type { AgentEvent, AgentName, RunInfo } from "../api";
import { currentActivity, toFeed, type FeedLine } from "../feed";
import { SPECIALISTS, STAFF, TOOL_HINT } from "../staff";
import { Badge } from "./Badge";

interface Props {
  run: RunInfo | null;
  events: AgentEvent[];
  starting: boolean;
}

function argText(args: Record<string, unknown> | string | null) {
  if (!args) return "";
  if (typeof args === "string") return args;
  return Object.entries(args)
    .map(([k, v]) => `${k}=${typeof v === "string" ? `"${v.length > 60 ? v.slice(0, 57) + "…" : v}"` : JSON.stringify(v)}`)
    .join(", ");
}

function Line({ line }: { line: FeedLine }) {
  const s = STAFF[line.agent];
  const style = { "--dept": s.color, "--depth": line.depth } as CSSProperties;
  const who = <span className="log__who">{s.title}</span>;
  switch (line.kind) {
    case "start":
      return (
        <li className="log__line log__line--start" style={style}>
          {who} {line.depth === 0 ? "picked up the ticket" : "clocked in"}
          {line.task && <q className="log__task">{line.task}</q>}
        </li>
      );
    case "tool":
      return (
        <li className="log__line log__line--tool" style={style}>
          {who} {TOOL_HINT[line.tool] ?? "used a tool"}
          <code className="log__call">
            {line.tool}({argText(line.args)})
          </code>
        </li>
      );
    case "result":
      return (
        <li className="log__line log__line--result" style={style}>
          <code>{line.tool}</code> returned <span className="log__result">{line.result.length > 160 ? line.result.slice(0, 157) + "…" : line.result}</span>
        </li>
      );
    case "handoff":
      return (
        <li className={`log__line log__line--handoff ${line.allowed ? "" : "is-refused"}`} style={style}>
          {who} handed off to <Badge agent={line.to} size="chip" />
          <q className="log__task">{line.task}</q>
          {!line.allowed && <span className="log__refused">Refused: {line.error}</span>}
        </li>
      );
    case "say":
      return (
        <li className="log__line log__line--say" style={style}>
          {who}: <span>{line.text}</span>
        </li>
      );
    case "done":
      return (
        <li className="log__line log__line--done" style={style}>
          {who} {line.stop === "final_output" ? "reported back" : `stopped (${line.stop})`}
          {line.summary && <span className="log__summary">{line.summary}</span>}
        </li>
      );
  }
}

// The shop floor: who's working right now, and a running log of what each agent did and which MCP tools it used.
export function LiveFloor({ run, events, starting }: Props) {
  const feed = useMemo(() => toFeed(events), [events]);
  const { active, working, doing } = useMemo(() => currentActivity(events), [events]);
  const running = run?.status === "running";
  const logRef = useRef<HTMLOListElement>(null);
  const toolCount = feed.filter((l) => l.kind === "tool").length;

  useEffect(() => {
    const el = logRef.current;
    if (el && running) el.scrollTop = el.scrollHeight;
  }, [feed.length, running]);

  const onFloor = (a: AgentName) => running && (active === a || working.has(a));

  return (
    <section className="floor" aria-labelledby="floor-title">
      <header className="floor__head">
        <h2 id="floor-title" className="section-title">On the floor</h2>
        {run && (
          <p className={`floor__status floor__status--${run.status}`}>
            {run.status === "running" && <><span className="spinner" aria-hidden="true" /> Team working ticket {run.ticket_id}</>}
            {run.status === "completed" && <>Ticket {run.ticket_id} run finished</>}
            {run.status === "failed" && <>Ticket {run.ticket_id} run stopped with an error</>}
            <span className="floor__runid">run {run.run_id}</span>
          </p>
        )}
      </header>

      <div className="roster">
        <div className="roster__boss">
          <Badge agent="boss" active={running && active === "boss"} working={onFloor("boss") && active !== "boss"} />
        </div>
        <div className="roster__team">
          {SPECIALISTS.map((a) => (
            <Badge key={a} agent={a} active={running && active === a} working={onFloor(a) && active !== a} />
          ))}
        </div>
      </div>

      <div className="now" aria-live="polite">
        {starting && <p>Dispatching the team…</p>}
        {!starting && running && active && (
          <p>
            <b style={{ color: STAFF[active].color }}>{STAFF[active].title}</b> is working: {doing}
          </p>
        )}
        {!starting && running && !active && <p>Waiting for the boss to pick up the ticket…</p>}
        {!starting && !running && !run && <p>Nobody's on the floor. Pick a ticket and send the team.</p>}
        {!starting && run && !running && (
          <p>
            Floor is quiet. {feed.filter((l) => l.kind === "handoff" && l.allowed).length} handoffs, {toolCount} MCP tool calls in the last run.
          </p>
        )}
      </div>

      <ol className="log" ref={logRef} aria-label="Agent activity log">
        {feed.map((line, i) => (
          <Line key={i} line={line} />
        ))}
        {running && <li className="log__line log__line--pending">…</li>}
      </ol>
    </section>
  );
}
