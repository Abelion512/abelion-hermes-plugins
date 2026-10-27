"""shield_abelion — pre_tool_call: read-before-edit, safety, loop, circuit breaker."""

from __future__ import annotations
import logging
from pathlib import Path
from .safety_guard import check_and_block as safety_check_block
from .safety_guard import check_and_block_read_before_edit, record_read
from .loop_detector import check_and_block as loop_check_block, reset_detector
from .circuit_breaker import on_tool_result as cb_on_tool_result
from .circuit_breaker import check_and_block as cb_check_block

logger = logging.getLogger(__name__)

_SKILL_DESCRIPTIONS = {
    "blocked-tool-recovery": "What to do when shield-abelion blocks a tool call.",
}

def _register_skills(ctx):
    """Register bundled skills/*/SKILL.md via ctx.register_skill (host >= 0.21.x).

    Guarded: on a host without ctx.register_skill the plugin still loads,
    only the skills are skipped. Skills appear as 'shield-abelion:<name>'
    in skills_list and the session <available_skills> index while enabled.
    """
    register_skill = getattr(ctx, "register_skill", None)
    if register_skill is None:
        logger.info("[shield_abelion] host has no ctx.register_skill; bundled skills skipped")
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

def _hook(tool_name, args, **kwargs):
    session_id = kwargs.get("session_id", "")
    if not isinstance(tool_name,str) or not tool_name.strip() or not isinstance(args,dict):
        return {"action":"block","message":"Tool name and object arguments are required."}
    if tool_name in {"read_file","write_file","edit","patch","write"}:
        target=args.get("path") or args.get("file_path") or args.get("target")
        if not isinstance(target,str) or not target.strip() or target in {".","/"}:
            return {"action":"block","message":"A specific file path is required; no value was changed."}
    block = check_and_block_read_before_edit(tool_name, args, session_id=session_id)
    if block: return block
    block = safety_check_block(tool_name, args)
    if block: return block
    block = loop_check_block(tool_name, args, session_id=session_id)
    if block: return block
    block = cb_check_block(tool_name, args)
    if block: return block
    return None

def _result(tool_name, status, args=None, session_id="", **kwargs):
    cb_on_tool_result(tool_name,status,**kwargs)
    # A requested or failed read is not evidence that the file was read.
    if tool_name == "read_file" and status in {"ok","success"} and isinstance(args,dict):
        path=args.get("path") or args.get("file_path")
        if isinstance(path,str) and path.strip():record_read(session_id,path)

def _snapshot(**kw):
    from .circuit_breaker import snapshot as cb_snap
    from .loop_detector import snapshot as ld_snap
    from .safety_guard import snapshot as sg_snap
    return {"circuit_breaker": cb_snap(), "loop_detector": ld_snap(), "read_history": sg_snap()}

def register(ctx):
    ctx.register_hook("pre_tool_call", _hook)
    ctx.register_hook("post_tool_call", _result)
    ctx.register_hook("on_session_end", _snapshot)
    ctx.register_hook("on_session_finalize", _snapshot)
    _register_skills(ctx)
    logger.info("[shield_abelion] Shield registered: read-before-edit, safety, loop, circuit breaker")
