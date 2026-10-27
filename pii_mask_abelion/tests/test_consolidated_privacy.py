"""Unified install identity, held output ownership and restoration ordering."""
import importlib.util
import json
from pathlib import Path
from unittest.mock import patch
import pytest
from pii_mask_abelion.guard import Guard, MARKER, TOKEN
from pii_mask_abelion import register

ROOT=Path(__file__).resolve().parents[2]


def test_exactly_three_independent_manifests_and_catalog_entries():
    manifests=list(ROOT.rglob('plugin.yaml'))
    assert len(manifests)==3
    catalog=json.loads((ROOT/'hermes.json').read_text())['plugins']
    assert len(catalog)==3
    assert 'output-redact-abelion' not in {p['id'] for p in catalog}
    assert 'pii-mask-abelion' in {p['id'] for p in catalog}
    assert not (ROOT/'output_redact_abelion').exists()


def test_one_output_hook_and_one_required_policy_owner():
    class Context:
        def __init__(self):self.hooks=[];self.middleware=[];self.skills=[]
        def register_hook(self,name,callback,*,hold_stream=False):self.hooks.append((name,callback,hold_stream))
        def register_middleware(self,name,callback):self.middleware.append((name,callback))
        def register_skill(self,*args):self.skills.append(args)
    ctx=Context();register(ctx)
    outputs=[x for x in ctx.hooks if x[0]=='transform_llm_output']
    assert len(outputs)==1 and outputs[0][2] is True
    assert len([x for x in ctx.middleware if x[0]=='llm_privacy'])==1
    assert {x[0] for x in ctx.skills}=={'privacy-mask-placeholders','redacted-output-handling'}


def test_unified_native_redactor_failure_withholds():
    pytest.importorskip('agent.redact')
    with patch('agent.redact.redact_sensitive_text',side_effect=RuntimeError('synthetic')):
        assert Guard().output('ordinary',session_id='one',platform='cli')==MARKER


def test_native_output_before_cli_restore_and_api_remains_masked():
    pytest.importorskip('agent.redact')
    g=Guard();s=g.session('one');token=g.remember(s,'sample@example.com','PII')
    seen=[]
    def native(text):seen.append(text);return text
    with patch('agent.redact.redact_sensitive_text',side_effect=native):
        assert g.output(token,session_id='one',platform='cli')=='sample@example.com'
        assert g.output(token,session_id='one',platform='api')==token
    assert seen==[token,token]
    secret=g.remember(s,'synthetic-secret','SECRET')
    assert g.output(secret,session_id='one',platform='cli')==secret
    assert g.output(token,session_id='two',platform='cli')==MARKER
