"""Synthetic audit regressions: credential headers and JSON text indirection."""
import copy
import importlib
import json
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
Guard = importlib.import_module('pii_mask_abelion.guard').Guard
CANARY = 'SyntheticAuditValueZ9x7Q5v3'

@pytest.mark.parametrize('key', ['Authorization', 'Proxy-Authorization', 'AUTHORIZATION'])
@pytest.mark.parametrize('value', [CANARY, 'Bearer ' + CANARY, 'Basic ' + CANARY, 'x', 'https://example.test', 'none'])
def test_authorization_controls_deny_instead_of_silent_rewrite(key, value):
    req = {'model': 'm', 'messages': [{'role': 'user', 'content': 'hello'}], 'headers': {key: value}}
    before = copy.deepcopy(req)
    result = Guard().required_policy('request', request=req, session_id='auth')
    assert result['allow'] is False
    assert 'request' not in result
    assert req == before

@pytest.mark.parametrize('key', ['Authorization', 'Proxy-Authorization', 'authorization'])
def test_authorization_prose_masks_without_restoration(key):
    g = Guard(); s = g.session('s')
    text = f'{key}: {CANARY}'
    masked = g.text(text, s)
    assert CANARY not in masked
    assert all(e.kind == 'SECRET' for e in s.entries.values())
    assert text.startswith(key)

@pytest.mark.parametrize('where', ['content', 'arguments', 'nested', 'array', 'json_again'])
@pytest.mark.parametrize('name', ['HF_TOKEN', 'api_key', 'client_id', 'Authorization'])
def test_json_name_value_indirection(where, name):
    pair = {'name': name, 'value': CANARY, 'note': 'ordinary text'}
    node = [pair] if where == 'array' else {'nested': pair} if where == 'nested' else pair
    text = json.dumps(node)
    if where == 'json_again': text = json.dumps({'nested_json': text})
    req = {'model': 'm', 'messages': [{'role': 'tool', 'content': text}]}
    if where == 'arguments':
        req = {'model': 'm', 'messages': [{'role': 'assistant', 'content': None, 'tool_calls': [
            {'id': 'call_x', 'type': 'function', 'function': {'name': 'lookup', 'arguments': text}}]}]}
    before = copy.deepcopy(req)
    result = Guard().required_policy('request', request=req, session_id='pair')
    assert result['allow'] is True
    assert CANARY not in json.dumps(result['request'])
    assert 'ordinary text' in json.dumps(result['request'])
    assert req == before

@pytest.mark.parametrize('text', [
    'plain ordinary prose', '{broken json', ' [ 1, 2, {"name": "model", "value": "ordinary"} ] ',
    '{"name": "api_key_name", "value": "ordinary"}', '{"name": "compass", "value": "ordinary"}',
    '{"ordinary": {"role": "user", "model": "fake-model", "count": 2}}',
])
def test_benign_or_malformed_json_preserved_byte_for_byte(text):
    req = {'model': 'm', 'messages': [{'role': 'user', 'content': text}]}
    result = Guard().required_policy('request', request=req, session_id='benign')
    assert result == {'allow': True, 'request': req}


def test_json_unknown_placeholder_does_not_become_trusted():
    text = json.dumps({'name': 'api_key', 'value': '<HG:' + 'a'*24 + ':' + 'b'*24 + '>'})
    result = Guard().required_policy('request', request={'model': 'm', 'messages': [{'content': text}]}, session_id='foreign')
    assert result['allow'] is False


def test_json_depth_is_bounded():
    text = '"x"'
    for _ in range(80): text = '{"nest":' + text + '}'
    result = Guard().required_policy('request', request={'model': 'm', 'messages': [{'content': text}]}, session_id='deep')
    assert result['allow'] is False


def test_repairs_through_actual_hermes_cli_and_local_server(tmp_path):
    import shutil
    pytest.importorskip('tests.fakes.fake_llm_provider')
    from tests.fakes.fake_llm_provider import FakeLLMServer, Text, ToolCall, write_hermes_home
    from tests.e2e.core.security._helpers import run_hermes
    home = tmp_path / 'home' / '.hermes'
    source = Path(__file__).resolve().parents[1]
    shutil.copytree(source, home / 'plugins' / 'pii_mask_abelion',
                    ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
    pair = json.dumps({'name': 'HF_TOKEN', 'value': CANARY, 'note': 'benign-retained'})
    prompt = 'Authorization: ' + CANARY + '\n' + pair
    # Fake model emits only a local printf of synthetic data. The following
    # provider request must mask the replayed JSON tool result too.
    command = "printf '%s' '" + pair + "'"
    with FakeLLMServer([ToolCall('terminal', {'command': command}), Text('done')]) as server:
        write_hermes_home(home, server.base_url, extra_config=(
            'plugins:\n  enabled:\n    - pii-mask-abelion\nupdates:\n  check: false\n'))
        result = run_hermes(['chat', '-q', prompt, '-Q'], tmp_path / 'home', cwd=tmp_path, timeout=90)
        requests = server.main_requests()
        all_requests = [r['body'] for r in server.requests]
    assert result.returncode == 0, result.stderr[-2000:]
    assert len(requests) == 2, (result.stdout[-1500:], requests)
    wire = json.dumps(requests)
    assert CANARY not in wire
    assert 'benign-retained' in wire
    assert any(m.get('role') == 'tool' for m in requests[-1]['messages'])
    # Main official host's auxiliary title call remains a separate known gap.
    (tmp_path / 'provider-main-count.txt').write_text(str(len(requests)))
