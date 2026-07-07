"""Context reminder — pre_llm_call hook.

Inject per-turn context: datetime, tool availability, execution mandate.
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
# Compact, grouped by use case. Update saat plugin list berubah.
_TOOL_MAP = """
• web: web_research, web_extract
• doc internal: knowledge_search (RAG)
• jadwal: schedule_add, schedule_list, schedule_remove
• goal: evey_goals
• model lain: delegate_with_model, delegate_parallel
• belajar: learn_from_interaction, reflect_on_output, validate_output
• memory: memory_search (hindsight recall)
""".strip()

_CONTEXT_TEMPLATE = """\
[Context: {datetime}
You can execute ALL of the following yourself via tools — NEVER ask the user to run commands on their terminal.
{tools}
Before making a plan, first scan available tools (the complete list is in your system prompt). 
Plan around what tools you actually have, not hypothetical steps.]"""


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
    context = _CONTEXT_TEMPLATE.format(datetime=now, tools=_TOOL_MAP)

    return {"context": context}
