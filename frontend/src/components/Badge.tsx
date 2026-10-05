import type { CSSProperties } from "react";
import type { AgentName } from "../api";
import { STAFF } from "../staff";

interface Props {
  agent: AgentName;
  active?: boolean;
  working?: boolean;
  size?: "roster" | "chip";
}

// Staff lanyard badge. The boss gets the navy manager badge; specialists get department colors.
export function Badge({ agent, active = false, working = false, size = "roster" }: Props) {
  const s = STAFF[agent];
  const boss = agent === "boss";
  if (size === "chip") {
    return (
      <span className={`chip ${boss ? "chip--boss" : ""}`} style={{ "--dept": s.color } as CSSProperties}>
        <span className="chip__dot" aria-hidden="true">{s.initials}</span>
        {s.title}
      </span>
    );
  }
  return (
    <div
      className={`badge ${boss ? "badge--boss" : ""} ${active ? "is-active" : ""} ${working ? "is-working" : ""}`}
      style={{ "--dept": s.color } as CSSProperties}
      aria-label={`${s.title}${active ? ", working now" : working ? ", waiting on a teammate" : ""}`}
    >
      <span className="badge__clip" aria-hidden="true" />
      <span className="badge__band">{boss ? "Manager" : s.desk}</span>
      <span className="badge__mono" aria-hidden="true">{s.initials}</span>
      <span className="badge__name">{s.title}</span>
      <span className="badge__state">{active ? "Working" : working ? "Waiting" : "Off the floor"}</span>
    </div>
  );
}
