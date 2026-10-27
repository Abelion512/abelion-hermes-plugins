"""rsi_learn_abelion — pre_llm_call + post_tool_call: RSI lesson extraction."""

from __future__ import annotations
import logging
from pathlib import Path
from .callback_hooks import pre_llm_hook, post_tool_call_hook
from .decision_hook import realtime_decision_hook

logger = logging.getLogger(__name__)

_SKILL_DESCRIPTIONS = {
    "experience-lessons": "Apply injected RSI lessons and realtime search context.",
}

def _register_skills(ctx):
    """Register bundled skills/*/SKILL.md via ctx.register_skill (guarded for old hosts)."""
    register_skill = getattr(ctx, "register_skill", None)
    if register_skill is None:
        logger.info("[rsi_learn_abelion] host has no ctx.register_skill; bundled skills skipped")
        return
    skills_dir = Path(__file__).resolve().parent / "skills"
    if not skills_dir.is_dir():
        return
    for child in sorted(skills_dir.iterdir()):
        skill_md = child / "SKILL.md"
        if child.is_dir() and skill_md.is_file():
            register_skill(
                name=child.name,
                path=skill_md,
                description=_SKILL_DESCRIPTIONS.get(child.name, ""),
            )

def register(ctx):
    ctx.register_hook("pre_llm_call", pre_llm_hook)
    ctx.register_hook("post_tool_call", post_tool_call_hook)
    ctx.register_hook("pre_llm_call", realtime_decision_hook)
    _register_skills(ctx)
    logger.info("[rsi_learn_abelion] RSI lesson hooks registered")
