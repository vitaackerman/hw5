"""Append-only audit trail of every agent-loop step, saved to output/audit_trail.json.

Logs who acted, tool calls/delegations with short args and results, and stop
reasons. Model "thinking" parts are never stored.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.config import AUDIT_TEXT_LIMIT


def short(value: Any, limit: int = AUDIT_TEXT_LIMIT) -> str:
    text = value if isinstance(value, str) else json.dumps(value, default=str, separators=(",", ":"))
    return text if len(text) <= limit else text[: limit - 3] + "..."


class AuditTrail:
    def __init__(self, path: Path):
        self.path = path
        self._lock = asyncio.Lock()

    async def log(self, *, run_id: str, agent: str, chain: tuple[str, ...], event: str, step: int | None = None, **details: Any) -> None:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "run_id": run_id,
            "agent": agent,
            "chain": " > ".join(chain),
            "depth": len(chain) - 1,
            "step": step,
            "event": event,
            **details,
        }
        async with self._lock:
            entries = json.loads(self.path.read_text(encoding="utf-8") or "[]") if self.path.exists() else []
            entries.append(entry)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
            tmp.replace(self.path)
