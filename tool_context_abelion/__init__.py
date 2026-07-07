"""tool_context_abelion — pre_llm_call: inject datetime + tool reminder + execution mandate."""

from __future__ import annotations
import logging
from .tool_reminder import tool_reminder

logger = logging.getLogger(__name__)

def register(ctx):
    ctx.register_hook("pre_llm_call", tool_reminder)
    logger.info("[tool_context_abelion] Tool context reminder hook registered")
