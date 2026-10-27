"""tool_context_abelion — pre_llm_call: inject datetime + tool reminder + execution mandate."""

from __future__ import annotations
import logging
from pathlib import Path
from .tool_reminder import tool_reminder

logger = logging.getLogger(__name__)

_SKILL_DESCRIPTIONS = {
    "turn-context": "Use the injected per-turn datetime and tool reminder.",
}

def _register_skills(ctx):
    """Register bundled skills/*/SKILL.md via ctx.register_skill (guarded for old hosts)."""
    register_skill = getattr(ctx, "register_skill", None)
    if register_skill is None:
        logger.info("[tool_context_abelion] host has no ctx.register_skill; bundled skills skipped")
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
    ctx.register_hook("pre_llm_call", tool_reminder)
    _register_skills(ctx)
    logger.info("[tool_context_abelion] Tool context reminder hook registered")
