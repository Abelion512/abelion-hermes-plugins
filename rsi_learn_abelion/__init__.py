"""rsi_learn_abelion — pre_llm_call + post_tool_call: RSI lesson extraction."""

from __future__ import annotations
import logging
from .callback_hooks import pre_llm_hook, post_tool_call_hook
from .decision_hook import realtime_decision_hook

logger = logging.getLogger(__name__)

def register(ctx):
    ctx.register_hook("pre_llm_call", pre_llm_hook)
    ctx.register_hook("post_tool_call", post_tool_call_hook)
    ctx.register_hook("pre_llm_call", realtime_decision_hook)
    logger.info("[rsi_learn_abelion] RSI lesson hooks registered")
