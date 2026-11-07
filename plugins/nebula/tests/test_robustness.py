"""Robustness: missing host symbols, missing payload fields and host failures fail closed.

Each test names a production behavior; none invent detection coverage.
"""
import builtins
import importlib
import json
import types
from nebula.guard import Guard, MARKER
from nebula import register


def test_missing_native_prefix_detector_symbol_keeps_local_masking(monkeypatch):
    """agent.redact present but _PREFIX_RE unusable: local patterns still mask."""
    fake = types.ModuleType('agent.redact')
    fake._PREFIX_RE = object()
    original = builtins.__import__
    def importing(name, *args, **kwargs):
        if name == 'agent.redact':
            return fake
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', importing)
    g = Guard()
    out = g.text('api_key=SuperSecretValue99', g.session('prefix-case'))
    assert 'SuperSecretValue99' not in out and out != 'api_key=SuperSecretValue99'


def test_required_policy_output_phase_with_missing_response_text_returns_marker():
    result = Guard().required_policy('output', session_id='missing-key')
    assert result == {'allow': True, 'response_text': MARKER}


def test_close_accepts_unhashable_session_identity_without_raising():
    g = Guard()
    g.session('keepme')
    g.close(session_id={'unhashable': 'id'})
    assert 'keepme' in g.sessions


def test_pii_middleware_walk_failure_never_returns_original_request(monkeypatch):
    pii = importlib.import_module('nebula.pii_middleware')
    request = {'messages': [{'role': 'user', 'content': 'api_key=SuperSecretValue99'}]}
    def boom(*args, **kwargs):
        raise RuntimeError('synthetic')
    monkeypatch.setattr(pii, '_mask_obj', boom)
    monkeypatch.setattr(pii, 'mask_content', lambda text: ('NOT-JSON', 1))
    result = pii.pii_middleware(request)
    assert result is not None
    assert result.get('request') != request
    assert 'SuperSecretValue99' not in json.dumps(result)


def test_mask_value_for_key_ignores_non_string_values():
    from nebula._credentials import mask_value_for_key
    assert mask_value_for_key('api_key', 12345) == (12345, 0)


def test_register_survives_and_logs_skill_registration_failure(caplog):
    import logging

    class Context:
        def __init__(self):
            self.hooks = []; self.middleware = []; self.skills = []
        def register_hook(self, name, callback, *, hold_stream=False):
            self.hooks.append((name, callback, hold_stream))
        def register_middleware(self, name, callback):
            self.middleware.append((name, callback))
        def register_skill(self, *args):
            raise RuntimeError('synthetic skill failure')
    ctx = Context()
    with caplog.at_level(logging.ERROR, logger='nebula'):
        register(ctx)
    assert len([x for x in ctx.middleware if x[0] == 'llm_request']) == 1
    assert len([x for x in ctx.middleware if x[0] == 'llm_privacy']) == 1
    assert len([x for x in ctx.middleware if x[0] == 'llm_execution']) == 1
    assert len([x for x in ctx.hooks if x[0] == 'transform_llm_output']) == 1
    assert 'Failed to register optional Nebula skill privacy-mask-placeholders' in caplog.text
