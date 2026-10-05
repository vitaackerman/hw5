import type { AgentEvent, AgentName, AgentReportDigest } from "./api";

export type FeedLine =
  | { kind: "start"; agent: AgentName; depth: number; task: string | null; ts: string }
  | { kind: "tool"; agent: AgentName; depth: number; tool: string; args: Record<string, unknown> | string | null; ts: string }
  | { kind: "result"; agent: AgentName; depth: number; tool: string; result: string; ts: string }
  | { kind: "handoff"; agent: AgentName; depth: number; to: AgentName; task: string; allowed: boolean; error: string | null; ts: string }
  | { kind: "say"; agent: AgentName; depth: number; text: string; ts: string }
  | { kind: "done"; agent: AgentName; depth: number; summary: string | null; stop: string | null; ts: string };

export function parseArgs(raw: string | null): Record<string, unknown> | string | null {
  if (!raw) return null;
  try {
    const v = JSON.parse(raw);
    return v && typeof v === "object" ? v : raw;
  } catch {
    return raw; // truncated in the audit trail
  }
}

function summaryFrom(said: string | null): string | null {
  if (!said) return null;
  const parsed = parseArgs(said);
  if (parsed && typeof parsed === "object" && typeof parsed.summary === "string") return parsed.summary;
  return said;
}

// Turn raw audit events into lines a manager can read, in order.
export function toFeed(events: AgentEvent[]): FeedLine[] {
  const lines: FeedLine[] = [];
  const seenTasks = new Map<string, string>(); // chain -> task, from the delegation that started it
  for (const e of events) {
    const base = { agent: e.agent, depth: e.depth, ts: e.ts };
    switch (e.type) {
      case "delegation":
        if (e.delegation) {
          lines.push({ kind: "handoff", ...base, to: e.delegation.to_agent, task: e.delegation.task,
            allowed: e.delegation.allowed, error: e.delegation.error });
          if (e.delegation.allowed) seenTasks.set(`${e.chain} > ${e.delegation.to_agent}`, e.delegation.task);
        }
        break;
      case "agent_start":
        lines.push({ kind: "start", ...base, task: seenTasks.get(e.chain) ?? null });
        break;
      case "model_response":
        for (const t of e.mcp_tools) lines.push({ kind: "tool", ...base, tool: t.tool, args: parseArgs(t.args) });
        if (e.said && !e.said.startsWith("{")) lines.push({ kind: "say", ...base, text: e.said });
        break;
      case "model_request":
        for (const t of e.mcp_tools) if (t.result) lines.push({ kind: "result", ...base, tool: t.tool, result: t.result });
        break;
      case "agent_stop":
        lines.push({ kind: "done", ...base, summary: e.report?.summary ?? summaryFrom(e.said), stop: e.stop_reason });
        break;
    }
  }
  return lines;
}

export interface Activity {
  agent: AgentName;
  doing: string;
}

// Who is working right now (deepest agent that has started but not stopped) and what they're doing.
export function currentActivity(events: AgentEvent[]): { active: AgentName | null; working: Set<AgentName>; doing: string | null } {
  const stack: AgentEvent[] = [];
  let last: AgentEvent | null = null;
  for (const e of events) {
    if (e.type === "agent_start") stack.push(e);
    if (e.type === "agent_stop") stack.pop();
    last = e;
  }
  const top = stack[stack.length - 1];
  if (!top) return { active: null, working: new Set(), doing: null };
  const working = new Set(stack.map((s) => s.agent));
  let doing = "Reading the task";
  const mine = last && last.agent === top.agent ? last : null;
  if (mine) {
    if (mine.type === "model_response" && mine.mcp_tools.length) doing = `Using ${mine.mcp_tools.map((t) => t.tool).join(", ")}`;
    else if (mine.type === "model_request") doing = mine.mcp_tools.length ? "Reading tool results" : "Working it out";
    else if (mine.type === "delegation" && mine.delegation) doing = `Handing off to ${mine.delegation.to_agent.replace("_", " ")}`;
  }
  return { active: top.agent, working, doing };
}

export interface AgentShift {
  agent: AgentName;
  report: AgentReportDigest;
  tools: string[];
}

// One entry per agent stop, in the order they finished, with the MCP tools that agent used.
export function shiftReport(events: AgentEvent[]): AgentShift[] {
  const tools = new Map<string, Set<string>>();
  const out: AgentShift[] = [];
  for (const e of events) {
    if (e.type === "model_response") {
      const set = tools.get(e.chain) ?? new Set();
      e.mcp_tools.forEach((t) => set.add(t.tool));
      tools.set(e.chain, set);
    }
    if (e.type === "agent_stop" && e.stop_reason === "final_output") {
      out.push({ agent: e.agent, report: e.report ?? { summary: summaryFrom(e.said) ?? "" }, tools: [...(tools.get(e.chain) ?? [])] });
    }
  }
  return out;
}
