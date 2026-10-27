import sys,os,tempfile,importlib.util,json,asyncio,types
from pathlib import Path
from unittest.mock import patch
import pytest
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));os.environ['HERMES_HOME']=tempfile.mkdtemp(prefix='algo-tests-')
from pii_mask_abelion.guard import Guard
import shield_abelion as shield
from output_redact_abelion.output_redact import redact_output
from tool_context_abelion.tool_reminder import tool_reminder
from rsi_learn_abelion import decision_hook as decision
spec=importlib.util.spec_from_file_location('screen_api_test',BASE/'screen/dashboard/plugin_api.py');screen=importlib.util.module_from_spec(spec);spec.loader.exec_module(screen)
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
def test_read_intent_is_not_success():
 sid='algo';file=Path(tempfile.mkstemp()[1]);args={'path':str(file)};shield._hook('read_file',args,session_id=sid)
 assert shield._hook('patch',args,session_id=sid)['action']=='block'
 shield._result('read_file','error',args,session_id=sid);assert shield._hook('patch',args,session_id=sid)['action']=='block'
 shield._result('read_file','ok',args,session_id=sid);assert shield._hook('patch',args,session_id=sid) is None
@pytest.mark.parametrize('args',[None,[],{'path':12},{'path':'/'},{'path':''}])
def test_shield_bad_values(args):assert shield._hook('patch',args,session_id='x')['action']=='block'
@pytest.mark.parametrize('value',[{},[],12])
def test_output_invalid(value):assert redact_output(value)=='[OUTPUT_WITHHELD:invalid_text]'
def test_output_native_failure():
 with patch('agent.redact.redact_sensitive_text',side_effect=RuntimeError('private')):
  assert redact_output('plain')=='[OUTPUT_WITHHELD:redactor_failed]'
def test_context_does_not_invent_tools():
 text=tool_reminder(user_message='test')['context'];assert 'execute ALL' not in text and 'delegate_parallel' not in text
 assert 'terminal' in tool_reminder(user_message='x',available_tools=['terminal'])['context']
@pytest.mark.parametrize('value',[{},[],12])
def test_rsi_invalid_query_no_effect(value):
 with patch.object(decision,'_ensure_store',side_effect=AssertionError):assert decision.realtime_decision_hook(user_message=value) is None
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
@pytest.mark.parametrize('status',['blocked','cancelled','timeout','',None,42])
def test_rsi_nonterminal_status_not_success(status):
 from rsi_learn_abelion import callback_hooks as hooks
 hooks._reset_session();before=dict(hooks._session_metrics)
 hooks.post_tool_call_hook(tool_name='read_file',status=status)
 assert hooks._session_metrics==before

def test_rsi_search_results_data_not_authority():
 class Store:
  def _read_all(self):return []
 with patch('tools.web_tools.web_search_tool',return_value=json.dumps({'success':True,'data':{'web':[{'title':'x','url':'https://example.org','description':'description'}]}})),patch.object(decision,'_ensure_store',return_value=Store()):
  text=decision.realtime_decision_hook(user_message='latest price')['context']
 assert 'SYSTEM OVERRIDE' not in text and 'untrusted source data' in text
def test_native_post_hook_ok_grants_read_only_after_result():
 import model_tools
 import hermes_cli.lifecycle as lifecycle
 sid='nativehook';file=Path(tempfile.mkstemp()[1]);args={'path':str(file)}
 shield._hook('read_file',args,session_id=sid)
 assert shield._hook('patch',args,session_id=sid)['action']=='block'
 def dispatch(name,**kw):
  assert name=='post_tool_call';assert kw['status']=='ok';shield._result(**kw)
 with patch.object(lifecycle,'has_hook',return_value=True),patch.object(lifecycle,'invoke_hook',side_effect=dispatch):
  model_tools._emit_post_tool_call_hook(function_name='read_file',function_args=args,result={'content':'read'},session_id=sid)
 assert shield._hook('patch',args,session_id=sid) is None

def test_native_ok_resets_breaker():
 from shield_abelion.circuit_breaker import get_breaker,on_tool_result,State
 cb=get_breaker('testnative');cb.record_failure();on_tool_result('testnative','ok');assert cb.failures==0 and cb.state==State.CLOSED
def test_existing_pr5_new_file_and_session_loops_preserved():
 from shield_abelion.loop_detector import reset_detector,check_and_block
 new=Path(tempfile.mkdtemp())/'newfile';assert shield._hook('write_file',{'path':str(new)},session_id='new') is None
 reset_detector()
 assert check_and_block('terminal',{'command':'a'},session_id='s1') is None
 assert check_and_block('terminal',{'command':'a'},session_id='s2') is None
 assert check_and_block('terminal',{'command':'a'},session_id='s1') is None
 assert check_and_block('terminal',{'command':'a'},session_id='s1')['action']=='block'

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
