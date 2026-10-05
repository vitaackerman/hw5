import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, type AgentEvent, type Cash, type PaymentRequest, type RunInfo, type TicketList } from "./api";

const RUN_POLL_MS = 1200;
const IDLE_POLL_MS = 8000;

// All desk state comes from the backend; the frontend never invents ticket or cash state.
export function useDesk() {
  const [tickets, setTickets] = useState<TicketList | null>(null);
  const [cash, setCash] = useState<Cash | null>(null);
  const [pending, setPending] = useState<PaymentRequest[]>([]);
  const [run, setRun] = useState<RunInfo | null>(null); // run shown on the floor (active or last viewed)
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [online, setOnline] = useState(true);
  const runRef = useRef<RunInfo | null>(null);
  runRef.current = run;

  const refreshDesk = useCallback(async () => {
    try {
      const [t, c, p] = await Promise.all([api.tickets(), api.cash(), api.paymentRequests()]);
      setTickets(t);
      setCash(c);
      setPending(p.pending);
      setOnline(true);
    } catch (e) {
      setOnline(false);
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  const loadRun = useCallback(async (runId: string) => {
    const [info, ev] = await Promise.all([api.run(runId), api.events(runId)]);
    setRun(info);
    setEvents(ev.events);
    return info;
  }, []);

  // First load: desk state, plus resume a run that was already going (e.g. after a page refresh).
  useEffect(() => {
    void (async () => {
      await refreshDesk();
      try {
        const health = await api.health();
        if (health.active_run) await loadRun(health.active_run);
        else {
          const runs = await api.runs();
          if (runs[0]) await loadRun(runs[0].run_id);
        }
      } catch {
        /* refreshDesk already reported the connection problem */
      }
    })();
  }, [refreshDesk, loadRun]);

  const running = run?.status === "running";

  // While a run is going, poll its events quickly; when it ends, refresh tickets, cash and approvals.
  useEffect(() => {
    if (!running || !run) return;
    let stop = false;
    const tick = async () => {
      try {
        const info = await loadRun(run.run_id);
        if (info.status !== "running") {
          await refreshDesk();
          return;
        }
        // Approvals can appear mid-run (request_payment), so keep the tray current too.
        const p = await api.paymentRequests();
        setPending(p.pending);
        setCash(p.cash);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }
      if (!stop) timer = window.setTimeout(tick, RUN_POLL_MS);
    };
    let timer = window.setTimeout(tick, RUN_POLL_MS);
    return () => {
      stop = true;
      window.clearTimeout(timer);
    };
  }, [running, run?.run_id, loadRun, refreshDesk]); // eslint-disable-line react-hooks/exhaustive-deps

  // When idle, keep the desk fresh in case something changed elsewhere (CLI run, approval in another tab).
  useEffect(() => {
    if (running) return;
    const id = window.setInterval(refreshDesk, IDLE_POLL_MS);
    return () => window.clearInterval(id);
  }, [running, refreshDesk]);

  const startRun = useCallback(
    async (ticketId: number) => {
      if (starting || runRef.current?.status === "running") return; // no duplicate dispatches
      setStarting(true);
      setError(null);
      try {
        const info = await api.runTicket(ticketId);
        setRun(info);
        setEvents([]);
      } catch (e) {
        setError(e instanceof ApiError && e.status === 409 ? `The team is busy: ${e.message}` : String((e as Error).message));
        // If another run is going, show it instead.
        const health = await api.health().catch(() => null);
        if (health?.active_run) await loadRun(health.active_run);
      } finally {
        setStarting(false);
      }
    },
    [starting, loadRun],
  );

  const viewRun = useCallback(
    async (runId: string) => {
      if (runRef.current?.status === "running") return;
      await loadRun(runId).catch((e) => setError(String(e.message)));
    },
    [loadRun],
  );

  const approve = useCallback(
    async (requestId: string, approvedBy: string) => {
      const result = await api.approve(requestId, approvedBy);
      setCash(result.cash);
      await refreshDesk();
      return result;
    },
    [refreshDesk],
  );

  const reject = useCallback(
    async (requestId: string, rejectedBy: string, reason: string) => {
      const result = await api.reject(requestId, rejectedBy, reason);
      setCash(result.cash);
      await refreshDesk();
    },
    [refreshDesk],
  );

  return {
    tickets,
    cash,
    pending,
    run,
    events,
    running,
    starting,
    online,
    error,
    clearError: () => setError(null),
    startRun,
    viewRun,
    approve,
    reject,
    refreshDesk,
  };
}
