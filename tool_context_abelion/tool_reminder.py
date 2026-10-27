"""Context reminder — pre_llm_call hook.

Inject per-turn datetime and verified tool-availability context.
Tujuan:
1. Date/time — cegah AI hallucination soal tanggal hari ini
2. Tool reminder — AI tau tools apa tersedia, jangan suruh user run command manual
3. Tool-first planning — sebelum planning, lihat tools dulu biar gak replan 2x
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# ── Tool manifest ──────────────────────────────────────────────────────
# Name tools only when the caller supplies a valid inventory.
_CONTEXT_TEMPLATE = """[Context: {datetime}
Use only tools actually available in the current session. Check their schemas and
required values before calling them. Wrong or unsupported values need correction,
not silent coercion. Do not claim a tool ran or ask the user to test portable work
that you can test yourself. Account access and approvals are separate requirements.
{tools}]"""


def tool_reminder(**kwargs: Any) -> dict[str, Any] | None:
    """pre_llm_call hook: inject datetime + tool context."""
    # Skip first turn — system prompt already has full tool list + datetime
    if kwargs.get("is_first_turn", False):
        return None

    # Skip empty/no-query messages
    user_message = kwargs.get("user_message", "")
    if not user_message or not isinstance(user_message, str):
        return None

    now = datetime.now(timezone.utc).strftime("%a %Y-%m-%d %H:%M UTC")
    available=kwargs.get("available_tools")
    if isinstance(available,list) and all(isinstance(n,str) and n.strip() for n in available):
        tools="Reported session tools: "+", ".join(dict.fromkeys(available))
    else:
        tools="No tool inventory supplied by this hook; use the host's session tool list."
    context = _CONTEXT_TEMPLATE.format(datetime=now, tools=tools)

    return {"context": context}
