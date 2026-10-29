"""A failing architectural boundary is an expected limitation, not a passing guard claim."""
import json,shutil
from pathlib import Path
import pytest
pytest.importorskip('tests.fakes.fake_llm_provider')
from tests.fakes.fake_llm_provider import FakeLLMServer,Text,write_hermes_home
from tests.e2e.core.security._helpers import run_hermes

@pytest.mark.xfail(strict=True, reason='Host auxiliary title call bypasses rewriting middleware; required core boundary missing')
def test_no_canary_in_any_provider_request(tmp_path):
    h=tmp_path/'home'/'.hermes';source=Path(__file__).resolve().parents[1]
    shutil.copytree(source,h/'plugins'/'pii_mask_abelion',ignore=shutil.ignore_patterns('__pycache__'))
    with FakeLLMServer([Text('done')]) as srv:
        write_hermes_home(h,srv.base_url,extra_config='plugins:\n  enabled:\n    - pii-mask-abelion\nupdates:\n  check: false\n')
        r=run_hermes(['chat','-q','api_key=AuditOpaqueZ9p4X6v8Q2','-Q'],tmp_path/'home',cwd=tmp_path,timeout=90)
        assert r.returncode==0 and len(srv.requests)>=2
        assert 'AuditOpaqueZ9p4X6v8Q2' not in json.dumps([x['body'] for x in srv.requests])
