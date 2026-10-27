"""Case changes preserve field meaning, including benign-name exclusions."""
import importlib
import itertools
import json
from pathlib import Path
import random
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
cred = importlib.import_module('pii_mask_abelion._credentials')
Guard = importlib.import_module('pii_mask_abelion.guard').Guard


def test_original_ten_classifier_repros():
    for name, expected in [
        ('password', 'SECRET'), ('paSsWOrD', 'SECRET'),
        ('service-password', 'SECRET'), ('SerViCE-PasSWord', 'SECRET'),
        ('client_id', 'IDENTIFIER'), ('aCcoUNT_SiD', 'IDENTIFIER'),
        ('compass', None), ('CoMPASs', None),
        ('api_key_name', None), ('API_key_nAme', None),
    ]:
        assert cred.classify_field(name) == expected, name


def test_every_case_spelling_of_short_secret_and_benign_names():
    for base, expected in [('password', 'SECRET'), ('compass', None),
                           ('api_key_name', None), ('account_sid', 'IDENTIFIER')]:
        variants = [(ch.lower(), ch.upper()) if ch.isalpha() else (ch,) for ch in base]
        for chars in itertools.product(*variants):
            name = ''.join(chars)
            assert cred.classify_field(name) == expected, name


def test_existing_camel_semantics_are_case_invariant():
    rng = random.Random(20261028)
    for base, expected in [
        ('clientSecret', 'SECRET'), ('githubToken', 'SECRET'),
        ('servicePassword', 'SECRET'), ('accessKey', 'SECRET'),
        ('secretKeyValue', 'SECRET'), ('clientId', 'IDENTIFIER'),
        ('appId', 'IDENTIFIER'), ('publicKey', 'IDENTIFIER'),
        ('accountSid', 'IDENTIFIER'), ('lmsEmail', 'IDENTIFIER'),
        ('apiKeyName', None), ('passwordPolicy', None),
        ('tokenCount', None), ('secretFile', None), ('tokenizer', None),
        ('filename', None), ('model', None), ('maxTokens', None),
        ('tokenSecret', 'SECRET'), ('apiKeyPrimary', 'SECRET'),
        ('apiGithubKey', 'SECRET'), ('countGithubToken', None),
        ('filePassword', None), ('perPassword', None), ('emailGithub', 'IDENTIFIER'),
        ('secretSidKey', 'SECRET'), ('fileNameToken', None),
    ]:
        for name in [base, base.lower(), base.upper()] + [
            ''.join(rng.choice((ch.lower(), ch.upper())) for ch in base)
            for _ in range(100)
        ]:
            assert cred.classify_field(name) == expected, name


def test_case_repair_reaches_real_request_policy_without_touching_metadata():
    for name, expected in [('paSsWOrD', True), ('SerViCE-PasSWord', True),
                           ('aCcoUNT_SiD', True), ('CoMPASs', False),
                           ('API_key_nAme', False)]:
        canary = 'SyntheticOpaqueZ9p4X6v8Q2'
        request = {'model': 'test-model', 'messages': [
            {'role': 'user', 'content': json.dumps({name: canary})}]}
        guard = Guard()
        result = guard.required_policy('request', request=request, session_id='case-test')
        assert result['allow'] is True
        assert (canary not in json.dumps(result['request'])) == expected, name
        assert canary in json.dumps(request)
        guard.close('case-test')


def test_long_chunk_does_not_recurse():
    assert cred.classify_field('ordinary' + 'id' * 2000) is None


def test_repaired_fields_through_real_hermes_cli(tmp_path):
    import shutil
    import pytest
    pytest.importorskip('tests.fakes.fake_llm_provider')
    from tests.fakes.fake_llm_provider import FakeLLMServer, Text, write_hermes_home
    from tests.e2e.core.security._helpers import run_hermes

    home = tmp_path / 'home' / '.hermes'
    source = Path(__file__).resolve().parents[1]
    shutil.copytree(source, home / 'plugins' / 'pii_mask_abelion',
                    ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
    secret = 'SyntheticOpaqueZ9p4X6v8Q2'
    benign = 'OrdinaryMetadataX7k8V2'
    prompt = json.dumps({'paSsWOrD': secret, 'aCcoUNT_SiD': secret,
                         'CoMPASs': benign, 'API_key_nAme': benign})
    with FakeLLMServer([Text('done')]) as server:
        write_hermes_home(home, server.base_url, extra_config=(
            'plugins:\n  enabled:\n    - pii-mask-abelion\n'
            'updates:\n  check: false\n'))
        result = run_hermes(['chat', '-q', prompt, '-Q'], tmp_path / 'home',
                            cwd=tmp_path, timeout=60)
        requests = server.main_requests()
    assert result.returncode == 0, result.stderr[-2000:]
    assert requests
    wire = json.dumps(requests)
    assert secret not in wire
    assert benign in wire
    # Auxiliary-call egress is checked by the separate known-boundary xfail.
