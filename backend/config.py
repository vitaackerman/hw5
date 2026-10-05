"""Model, paths, MCP connection and run limits for the agent team."""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from dotenv import load_dotenv
from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import UsageLimits

PROJECT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = PROJECT / "backend" / "prompts"
MCP_SERVER = PROJECT / "mcp_server" / "server.py"
AUDIT_PATH = Path(os.getenv("AUDIT_TRAIL_PATH", PROJECT / "output" / "audit_trail.json"))
ORIGINAL_DB = PROJECT / "data" / "campus_customs.db"  # never written; only copied for a reset
# Same env overrides the MCP server reads, so tests can point everything at scratch copies.
WORKING_DB = Path(os.getenv("CAMPUS_CUSTOMS_DB", PROJECT / "data" / "campus_customs_new.db")).resolve()
STATE_DIR = Path(os.getenv("CAMPUS_CUSTOMS_STATE_DIR", PROJECT / "output")).resolve()

# The key lives in the Coding/.env shared by every homework; nearest .env wins.
for folder in [PROJECT, *PROJECT.parents]:
    load_dotenv(folder / ".env")

PORTKEY_BASE_URL = "https://api.portkey.ai/v1"
MODEL_NAME = "gpt-6-luna"  # the only model this homework uses

# ---- limits that keep token and tool use bounded (one budget per team run) ----
TEAM_LIMITS = UsageLimits(
    request_limit=40,          # model calls across ALL agents in one run
    tool_calls_limit=60,       # MCP + delegate calls across all agents
    total_tokens_limit=400_000,
)
MAX_DELEGATION_DEPTH = 3       # longest chain, e.g. boss -> inventory -> accounting
MAX_DELEGATIONS = 8            # delegate calls per team run
AGENT_RETRIES = 2              # bad tool args / output validation retries per agent
MODEL_SETTINGS = {"timeout": 120, "max_tokens": 8000}  # per model response, reasoning included
AUDIT_TEXT_LIMIT = 300         # chars kept per logged argument/result

# Tools only a human may call (via backend/approve.py); never shown to agents.
HUMAN_ONLY_TOOLS = {"approve_payment", "reject_payment"}


class TeamNotConfigured(RuntimeError):
    pass


@lru_cache(maxsize=1)
def get_model() -> OpenAIResponsesModel:
    key = os.getenv("PORTKEY_API_KEY")
    if not key:
        raise TeamNotConfigured("PORTKEY_API_KEY is not set. Add it to the Coding/.env file.")
    # gpt-6-luna only supports function tools on the Responses API (/v1/responses), not chat completions.
    return OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(base_url=PORTKEY_BASE_URL, api_key=key))


def mcp_client() -> Client:
    """A FastMCP client that launches mcp_server/server.py over stdio with this venv's Python."""
    env = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "LANG") or k.startswith("CAMPUS_CUSTOMS_")}
    env["FASTMCP_LOG_LEVEL"] = "WARNING"  # keep the server's startup INFO lines out of the terminal
    return Client(StdioTransport(sys.executable, [str(MCP_SERVER)], env=env, cwd=str(PROJECT)))


@lru_cache(maxsize=1)
def mcp_toolset() -> MCPToolset:
    """One shared MCP connection for the whole team (enter it once per run)."""
    return MCPToolset(mcp_client(), id="campus-customs", max_retries=1)
