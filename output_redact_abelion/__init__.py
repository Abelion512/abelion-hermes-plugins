"""Final credential redaction, held before delivery."""
from .output_redact import redact_output

def register(ctx):
    import inspect
    if 'hold_stream' not in inspect.signature(ctx.register_hook).parameters:
        raise RuntimeError('Output redaction requires Hermes hold_stream support')
    ctx.register_hook('transform_llm_output',redact_output,hold_stream=True)

    register_skill = getattr(ctx, 'register_skill', None)
    if callable(register_skill):
        from pathlib import Path
        register_skill('redacted-output-handling', Path(__file__).parent / 'skills' / 'redacted-output-handling' / 'SKILL.md',
                       'Handle responses passed through credential redaction.')
