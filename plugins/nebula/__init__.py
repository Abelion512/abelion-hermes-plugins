"""Local request guard with session mapping and held final delivery."""
import logging

from .guard import GUARD

logger = logging.getLogger(__name__)
_stock_warned = False


def _core_required() -> bool:
    """Return True only when the host's required privacy policy is active."""
    try:
        from agent.privacy_guard import required
        return bool(required())
    except Exception:
        logger.debug("Could not confirm the pinned required privacy core is active", exc_info=True)
        return False

def register(ctx):
    # Refuse legacy hosts rather than silently running a leaking stream transform.
    import inspect
    if 'hold_stream' not in inspect.signature(ctx.register_hook).parameters:
        raise RuntimeError('Privacy guard requires Hermes hold_stream support')
    ctx.register_middleware('llm_privacy',GUARD.required_policy)
    ctx.register_middleware('llm_request',GUARD.optional_request)
    ctx.register_middleware('llm_execution',GUARD.execute)
    ctx.register_middleware('tool_request',GUARD.tool_request)
    ctx.register_hook('pre_tool_call',GUARD.pre_tool)
    ctx.register_hook('transform_llm_output',GUARD.output,hold_stream=True)
    ctx.register_hook('on_session_end',GUARD.close)
    if not _core_required():
        global _stock_warned
        if not _stock_warned:
            _stock_warned = True
            logger.warning(
                "Nebula optional mode: auxiliary/title provider calls are NOT guarded "
                "without the pinned required-policy core. Enable required mode with "
                "the matching Hermes core to protect auxiliary egress."
            )

    if hasattr(ctx,'register_system_prompt_section'):
        ctx.register_system_prompt_section('abelion.redact',
            'Privacy Guard (nebula) is loaded. Sensitive values may be session-bound '
            'placeholders. Copy tokens exactly, never change their case or guess originals. '
            'For local file work use read_file, write_file, patch or search_files path slots. '
            'Do not paste placeholders into terminal commands, URLs, messages or delegate goals. '
            'A refusal means stop and report the limit, not bypass the policy. '
            'Never claim all unknown secrets or network traffic are protected. '
            'Optional mode does not guard auxiliary/title provider calls; '
            'required mode with the pinned core is needed for those. '
            'Usage and current limits are in the plugin README.md.', max_chars=1000)

    register_skill = getattr(ctx, 'register_skill', None)
    if callable(register_skill):
        from pathlib import Path
        skills_dir = Path(__file__).parent / 'skills'
        # Skill surface is advisory: a missing file or a raising host API must not
        # abort core middleware registration. Skip one failure, keep the rest.
        for name, description in (
            ('privacy-mask-placeholders', 'Work with masked PII, credential and path placeholders.'),
            ('redacted-output-handling', 'Handle responses passed through credential redaction.'),
            ('nebula-plugin-setup', 'Set up, enable, roll back, and disable the nebula plugin.'),
            ('nebula-plugin-debug', 'Debug and reproduce nebula Privacy Guard failures.'),
        ):
            path = skills_dir / name / 'SKILL.md'
            if not path.is_file():
                logger.warning("Skipping missing optional skill file: %s", path)
                continue
            try:
                register_skill(name, path, description)
            except Exception:
                # Skill discovery is optional, but registration failures must be
                # visible to maintainers while core privacy hooks remain active.
                logger.exception("Failed to register optional Nebula skill %s", name)
