"""Actual CLI -> loopback HTTP provider. Never a real model or credential."""
import json,re,shutil
from pathlib import Path
import pytest
pytest.importorskip('tests.fakes.fake_llm_provider')
from tests.fakes.fake_llm_provider import FakeLLMServer,Text,ToolCall,write_hermes_home
from tests.e2e.core.security._helpers import run_hermes
SOURCE=Path(__file__).resolve().parents[2]
CANARIES=['sk-proj-Qm7Zk2Wp9Rt4Lx8aB3cD5eF6gH7','Zk7Qm2Wp9Rt4Lx8vN5','budi.santoso@gmail.com','0812-3456-7890','3174051203990001','4111 1111 1111 1111','Tq8Zp3Lm6Vx9Ra2Cs']

def install(home,both=False):
    names=['pii_mask_abelion']+(['output_redact_abelion'] if both else [])
    for p in names:shutil.copytree(SOURCE/p,home/'plugins'/p,ignore=shutil.ignore_patterns('__pycache__','.pytest_cache'))
    return 'plugins:\n  enabled:\n'+''.join('    - '+p.replace('_','-')+'\n' for p in names)+'updates:\n  check: false\nskills:\n  creation_nudge_interval: 0\nmemory:\n  nudge_interval: 0\n'

@pytest.mark.parametrize('both',[False,True])
def test_request_and_tool_replay(tmp_path,both):
    h=tmp_path/'home'/'.hermes';ws=tmp_path/'private-workspace';ws.mkdir()
    text=f'api_key={CANARIES[0]} acme_secret_blob={CANARIES[1]} email {CANARIES[2]} phone {CANARIES[3]} NIK {CANARIES[4]} card {CANARIES[5]} /home/abelion/private/project'
    script=[ToolCall('terminal',{'command':'printf "ok"; echo --token '+CANARIES[6]}),Text('openweather_api_key="Hy4Nb7Kd1Wf5Gz8Xe"')]
    with FakeLLMServer(script) as srv:
        write_hermes_home(h,srv.base_url,extra_config=install(h,both))
        result=run_hermes(['chat','-q',text,'-Q'],tmp_path/'home',cwd=ws,timeout=90)
        requests=srv.main_requests()
    assert result.returncode==0 and len(requests)==2,(result.stdout,result.stderr)
    wire=json.dumps(requests)
    assert all(v not in wire for v in CANARIES)
    assert '/home/abelion/private/project' not in wire and 'private-workspace' not in wire
    assert 'Hy4Nb7Kd1Wf5Gz8Xe' not in result.stdout


def test_placeholder_read_file_roundtrip(tmp_path):
    h=tmp_path/'home'/'.hermes';ws=tmp_path/'ws';ws.mkdir();file=ws/'local.txt';file.write_text('ROUNDTRIP_CONTENT_OK')
    def director(req):
        req=req['body'];
        if len([m for m in req['messages'] if m['role']=='tool']):return Text('read succeeded')
        user=next(m['content'] for m in req['messages'] if m['role']=='user')
        token=re.search(r'<HG:[0-9a-f]{24}:[0-9a-f]{24}>',user)[0]
        return ToolCall('read_file',{'path':token})
    with FakeLLMServer(director) as srv:
        write_hermes_home(h,srv.base_url,extra_config=install(h))
        r=run_hermes(['chat','-q','Read '+str(file),'-Q'],tmp_path/'home',cwd=ws,timeout=90)
        requests=srv.main_requests()
    assert r.returncode==0 and len(requests)==2,(r.stdout,r.stderr)
    assert str(file) not in json.dumps(requests)
    tools=[m['content'] for m in requests[-1]['messages'] if m['role']=='tool']
    assert any('ROUNDTRIP_CONTENT_OK' in t for t in tools),tools
