import sys,os,tempfile,importlib.util,json,asyncio,types

from pathlib import Path

from unittest.mock import patch

import pytest

pytest.importorskip("hermes_constants", reason="cross-plugin integration requires matching Hermes checkout; see docs/DELIVERY.md")

BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));os.environ['HERMES_HOME']=tempfile.mkdtemp(prefix='algo-tests-')

BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));os.environ['HERMES_HOME']=tempfile.mkdtemp(prefix='algo-tests-')

BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));os.environ['HERMES_HOME']=tempfile.mkdtemp(prefix='algo-tests-')

from pii_mask_abelion.guard import Guard

from pii_mask_abelion.output_redact import redact_output

spec=importlib.util.spec_from_file_location('screen_api_test',BASE/'screen/dashboard/plugin_api.py');screen=importlib.util.module_from_spec(spec);spec.loader.exec_module(screen)

spec=importlib.util.spec_from_file_location('screen_api_test',BASE/'screen/dashboard/plugin_api.py');screen=importlib.util.module_from_spec(spec);spec.loader.exec_module(screen)

spec=importlib.util.spec_from_file_location('screen_api_test',BASE/'screen/dashboard/plugin_api.py');screen=importlib.util.module_from_spec(spec);spec.loader.exec_module(screen)

spec=importlib.util.spec_from_file_location('nine_test',BASE/'model-providers/9router/__init__.py');nine=importlib.util.module_from_spec(spec)

spec=importlib.util.spec_from_file_location('nine_test',BASE/'model-providers/9router/__init__.py');nine=importlib.util.module_from_spec(spec)

with patch('urllib.request.urlopen',side_effect=OSError):spec.loader.exec_module(nine)

@pytest.mark.parametrize('kw',[{'ttl':float('nan')},{'ttl':0},{'max_sessions':True},{'max_entries':-1},{'max_bytes':'2'}])
def test_guard_wrong_requirement(kw):
 with pytest.raises(ValueError):Guard(**kw)

@pytest.mark.parametrize('req',[None,[],{}, {'model':'','messages':[{}]},{'model':'ok','messages':'wrong'}])
def test_guard_wrong_values_no_state(req):
 g=Guard();r=g.required_policy('request',request=req,session_id='s');assert r['allow'] is False;assert not g.sessions

@pytest.mark.parametrize('args',[None,[],42])
def test_tool_args_wrong_type(args):assert Guard().pre_tool(args)['action']=='block'

def test_guard_valid():
 r=Guard().required_policy('request',request={'model':'test','messages':[{'role':'user','content':'email=a@example.com'}]},session_id='s');assert r['allow'];assert 'a@example.com' not in json.dumps(r['request'])

@pytest.mark.parametrize('value',[{},[],12])
def test_output_invalid(value):assert redact_output(value)=='[OUTPUT_WITHHELD:invalid_text]'

def test_output_native_failure():
 with patch('agent.redact.redact_sensitive_text',side_effect=RuntimeError('private')):
  assert redact_output('plain')=='[OUTPUT_WITHHELD:redactor_failed]'

class Response:
 def __init__(self,value):self.value=value
 def __enter__(self):return self
 def __exit__(self,*args):pass
 def read(self,*args):return json.dumps(self.value).encode()

@pytest.mark.parametrize('data',[[],{'data':[{'id':[]},{'id':3},{'id':'bad id'}]}, {'data':'oops'}])
def test_nine_bad_model_values(data):
 with patch('urllib.request.urlopen',return_value=Response(data)):assert nine._fetch_models() is None

def test_nine_valid_unique():
 with patch('urllib.request.urlopen',return_value=Response({'data':[{'id':'oc/a'},{'id':'oc/a'}]})):assert nine._fetch_models()==['oc/a']

class Request:
 def __init__(self,raw):self.raw=raw
 async def body(self):return self.raw

@pytest.mark.parametrize('action,body',[('release',b'{'),('release',b'[]'),('release',b'{"force":"false"}'),('acquire',b'{"force":true}'),('release',b'{"unknown":1}')])
def test_screen_wrong_requirement_no_rpc(action,body):
 screen._viewer_id='mine'
 with patch.object(screen,'_rpc_call',side_effect=AssertionError):
  result=asyncio.run(screen.lease(Request(body),action));assert result.status_code==422

def test_screen_explicit_force_release_only():
 screen._viewer_id='mine';screen._rpc=None;calls=[]
 async def rpc(req,method,params=None):calls.append((method,params));return {'lease':{'holder':'agent'}}
 with patch.object(screen,'_rpc_call',side_effect=rpc):r=asyncio.run(screen.lease(Request(b'{"force":true}'),'release'))
 assert calls==[('display.lease.release',{'force':True})] and r['forced'] is True

def test_nine_auth_live_catalog_no_invented_routes(monkeypatch):
 monkeypatch.setenv('NINEROUTER_API_KEY','synthetic');seen=[]
 def request(req,**kw):seen.append(req);return Response({'data':[{'id':'new/model'},{'id':'combo-new'}]})
 monkeypatch.setattr(nine,'_discovered',None)
 with patch('urllib.request.urlopen',side_effect=request):assert nine.get_available_models()==['new/model','combo-new']
 assert seen[0].get_header('Authorization')=='Bearer synthetic'
 assert not any('*' in x for x in nine.get_available_models())

def test_nine_empty_live_is_empty_not_fallback(monkeypatch):
 monkeypatch.setattr(nine,'_discovered',None)
 with patch('urllib.request.urlopen',return_value=Response({'data':[]})):assert nine.get_available_models()==[]

def test_nine_refresh_after_ttl(monkeypatch):
 monkeypatch.setattr(nine,'_discovered',['stale/model']);monkeypatch.setattr(nine,'_discovered_at',0)
 monkeypatch.setattr(nine.time,'monotonic',lambda:100)
 with patch('urllib.request.urlopen',return_value=Response({'data':[{'id':'fresh/model'}]})):assert nine.get_available_models()==['fresh/model']

@pytest.mark.parametrize('payload',[{}, {'error':'unauthorized'}, {'data':None}])
def test_nine_missing_catalog_is_failure(payload):
 with patch('urllib.request.urlopen',return_value=Response(payload)):assert nine._fetch_models() is None
