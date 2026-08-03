#!/usr/bin/env python3
"""Regenerate tool-definitions.lock.json (SEC-022).

Run this whenever you intentionally change a tool's name, description, input/
output schema, or annotations — then commit the updated lock file and note the
change in CHANGELOG.md. The test `test_tool_definitions_match_lock` fails if the
live definitions drift from the lock without a regenerate, catching silent
"rug pull" tool mutations.

Usage:
    PYTHONPATH=src python scripts/snapshot_tools.py
"""

from __future__ import annotations

import asyncio
import json
from datetime import date
from pathlib import Path

from fedlex_mcp import server

LOCK_PATH = Path(__file__).resolve().parent.parent / "tool-definitions.lock.json"


async def main() -> None:
    digest = await server.compute_tool_signature_hash()
    tools = sorted(t.name for t in await server.mcp.list_tools())
    LOCK_PATH.write_text(
        json.dumps(
            {
                "sha256": digest,
                "tool_count": len(tools),
                "tools": tools,
                "generated_on": date.today().isoformat(),
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {LOCK_PATH.name}: {len(tools)} tools, sha256={digest[:16]}…")


if __name__ == "__main__":
    asyncio.run(main())
