"""shield_abelion — pre_tool_call: read-before-edit, safety, loop, circuit breaker."""

from __future__ import annotations
import logging
from .safety_guard import check_and_block as safety_check_block
from .safety_guard import check_and_block_read_before_edit, record_read
from .loop_detector import check_and_block as loop_check_block, reset_detector
from .circuit_breaker import on_tool_result as cb_on_tool_result
from .circuit_breaker import check_and_block as cb_check_block

logger = logging.getLogger(__name__)

def _hook(tool_name, args, **kwargs):
    session_id = kwargs.get("session_id", "")
    if tool_name == "read_file":
        read_path = str(args.get("path", "") or args.get("file_path", ""))
        if read_path:
            record_read(session_id, read_path)
    block = check_and_block_read_before_edit(tool_name, args, session_id=session_id)
    if block: return block
    block = safety_check_block(tool_name, args)
    if block: return block
    block = loop_check_block(tool_name, args, session_id=session_id)
    if block: return block
    block = cb_check_block(tool_name, args)
    if block: return block
    return None

def _snapshot(**kw):
    from .circuit_breaker import snapshot as cb_snap
    from .loop_detector import snapshot as ld_snap
    from .safety_guard import snapshot as sg_snap
    return {"circuit_breaker": cb_snap(), "loop_detector": ld_snap(), "read_history": sg_snap()}

def register(ctx):
    ctx.register_hook("pre_tool_call", _hook)
    ctx.register_hook("post_tool_call", cb_on_tool_result)
    ctx.register_hook("on_session_end", _snapshot)
    ctx.register_hook("on_session_finalize", _snapshot)
    logger.info("[shield_abelion] Shield registered: read-before-edit, safety, loop, circuit breaker")
