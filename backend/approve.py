"""Human approval of payment requests. Agents can't run this; it's for you.

Goes through the MCP server like everything else, calling its human-only
approve_payment / reject_payment tools.

From the HW5 folder:
    .venv/bin/python -m backend.approve list
    .venv/bin/python -m backend.approve approve PR-1 --by "Claire Levita"
    .venv/bin/python -m backend.approve reject PR-1 --by "Claire Levita" --reason "wait until Friday"
"""

from __future__ import annotations

import argparse
import asyncio
import json

from backend.config import mcp_client


async def _call(tool: str, args: dict) -> dict:
    async with mcp_client() as client:
        result = await client.call_tool(tool, args)
    return result.structured_content or json.loads(result.content[0].text)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="Show payment requests waiting for approval.")
    ok = sub.add_parser("approve", help="Approve and pay a request.")
    ok.add_argument("request_id")
    ok.add_argument("--by", required=True, help="Your name (recorded as approved_by).")
    no = sub.add_parser("reject", help="Reject a request; nothing is paid.")
    no.add_argument("request_id")
    no.add_argument("--by", required=True)
    no.add_argument("--reason", required=True)
    args = parser.parse_args()

    if args.cmd == "list":
        out = asyncio.run(_call("get_cash_and_obligations", {}))
        out = {"cash_accounts": out["cash_accounts"], "pending_payment_requests": out["pending_payment_requests"]}
    elif args.cmd == "approve":
        out = asyncio.run(_call("approve_payment", {"request_id": args.request_id, "approved_by": args.by}))
    else:
        out = asyncio.run(_call("reject_payment", {"request_id": args.request_id, "rejected_by": args.by, "reason": args.reason}))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
