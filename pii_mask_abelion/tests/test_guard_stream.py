import json, os, shutil
from pathlib import Path
import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
pytest.importorskip('gateway.config')
from gateway.config import PlatformConfig
from gateway.platforms.api_server import APIServerAdapter
fakes = pytest.importorskip("tests.fakes.fake_llm_provider", reason="Hermes integration harness required; run with the matching core checkout on PYTHONPATH")
FakeLLMServer, Text, write_hermes_home = fakes.FakeLLMServer, fakes.Text, fakes.write_hermes_home

GHP='ghp_Ab1Cd2Ef3Gh4Ij5Kl6Mn7Op8Qr9St0Uv1Wx2'
ANS=f'Here: token {GHP} and "openweather_api_key": "Hy4Nb7Kd1Wf5Gz8Xe" mail budi.santoso@gmail.com end.'
def _sse(body):
    return [json.loads(l[6:]) for l in body.splitlines() if l.startswith("data: ") and l!="data: [DONE]"]

@pytest.mark.asyncio
@pytest.mark.parametrize("label,pl,src", [("guard",["pii_mask_abelion"],str(Path(__file__).resolve().parents[2])),("both",["pii_mask_abelion","output_redact_abelion"],str(Path(__file__).resolve().parents[2]))])
async def test_probe(label,pl,src,tmp_path,monkeypatch):
    from hermes_cli import plugins
    home = tmp_path / "home" / ".hermes"
    monkeypatch.setenv("HERMES_HOME",str(home))
    with FakeLLMServer([Text(ANS, chunk_chars=6),Text(ANS, chunk_chars=6)]) as srv:
        extra="updates:\n  check: false\nskills:\n  creation_nudge_interval: 0\nmemory:\n  nudge_interval: 0\n"
        if pl:
            for p in pl: shutil.copytree(f"{src}/{p}", home/"plugins"/p, dirs_exist_ok=True)
            extra+="plugins:\n  enabled:\n"+"".join(f"    - {n.replace('_','-')}\n" for n in pl)
        write_hermes_home(home, srv.base_url, extra_config=extra)
        plugins._reset_plugin_managers_for_tests()
        adapter = APIServerAdapter(PlatformConfig(enabled=True, extra={}))
        app = web.Application(); app.router.add_post("/v1/chat/completions", adapter._handle_chat_completions)
        try:
            async with TestClient(TestServer(app)) as c:
                r = await c.post("/v1/chat/completions", json={"model":"fake-model","stream":True,"messages":[{"role":"user","content":"hi"}]})
                chunks=[x["choices"][0]["delta"].get("content") for x in _sse(await r.text()) if x.get("choices")]
                r2 = await c.post("/v1/chat/completions", json={"model":"fake-model","stream":False,"messages":[{"role":"user","content":"hi"}]})
                final=(await r2.json())["choices"][0]["message"]["content"]
        finally:
            plugins._reset_plugin_managers_for_tests()
    sj="".join(x for x in chunks if x)
    assert GHP not in sj and "Hy4Nb7Kd1Wf5Gz8Xe" not in sj and "budi.santoso@gmail.com" not in sj
    assert GHP not in final and "Hy4Nb7Kd1Wf5Gz8Xe" not in final and "budi.santoso@gmail.com" not in final
    def leaks(t): return {k:(v in t) for k,v in dict(ghp=GHP,jsonkey="Hy4Nb7Kd1Wf5Gz8Xe",email="budi.santoso@gmail.com").items()}
    print(f"\nPROBE joined_has_final_rewrite={('[REDACTED' in sj or '***' in sj)} " + f" {label}: stream_deltas={len(chunks)} stream_joined_raw={leaks(sj)} nonstream_final_raw={leaks(final)}")
