"""Dashboard plugin: the SCREEN tab is discovered via dashboard/manifest.json.

register() only publishes the bundled agent skills (skills/*/SKILL.md) through
ctx.register_skill; the plugin adds no tools or hooks. Hosts without
ctx.register_skill load the dashboard tab unchanged, without the skills.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_SKILL_DESCRIPTIONS = {
    "bot-screen-control": "Work with the Screen dashboard: view, Take over, Hand back.",
}


def register(ctx):
    register_skill = getattr(ctx, "register_skill", None)
    if register_skill is None:
        logger.info("[screen] host has no ctx.register_skill; bundled skills skipped")
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
