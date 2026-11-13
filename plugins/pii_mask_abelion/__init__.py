"""Local request guard with session mapping and held final delivery."""
from .guard import GUARD

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

    if hasattr(ctx,'register_system_prompt_section'):
        ctx.register_system_prompt_section('abelion.redact',
            'Privacy Guard (pii-mask-abelion) is loaded. Sensitive values may be session-bound '
            'placeholders. Copy tokens exactly, never change their case or guess originals. '
            'For local file work use read_file, write_file, patch or search_files path slots. '
            'Do not paste placeholders into terminal commands, URLs, messages or delegate goals. '
            'A refusal means stop and report the limit, not bypass the policy. '
            'Never claim all unknown secrets or network traffic are protected. '
            'Usage and current limits are in the plugin README.md.', max_chars=1000)

    register_skill = getattr(ctx, 'register_skill', None)
    if callable(register_skill):
        from pathlib import Path
        register_skill('privacy-mask-placeholders', Path(__file__).parent / 'skills' / 'privacy-mask-placeholders' / 'SKILL.md',
                       'Work with masked PII, credential and path placeholders.')
        register_skill('redacted-output-handling', Path(__file__).parent / 'skills' / 'redacted-output-handling' / 'SKILL.md',
                       'Handle responses passed through credential redaction.')
