"""Run the Campus Customs team on a task from the command line.

From the HW5 folder:
    .venv/bin/python -m backend.run "Review open tickets and report; change nothing."
    .venv/bin/python -m backend.run --agent inventory "Check stock for CC-TEE-WHITE size S."
"""

from __future__ import annotations

import argparse
import asyncio
import json

from backend.config import AUDIT_PATH
from backend.models import AGENT_NAMES
from backend.team import run_team


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("task", help="What the team should do.")
    parser.add_argument("--agent", choices=AGENT_NAMES, default="boss", help="Agent to start with (default: boss).")
    args = parser.parse_args()
    run_id, output = asyncio.run(run_team(args.task, start_with=args.agent))
    print(f"run_id: {run_id}  (steps logged to {AUDIT_PATH})")
    print(json.dumps(output.model_dump(), indent=2))


if __name__ == "__main__":
    main()
