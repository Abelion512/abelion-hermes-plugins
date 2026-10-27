import copy,json,re
import importlib.util
from pii_mask_abelion.guard import Guard,TOKEN,MARKER

def _expected_output(available, unavailable):
    try:
        import agent.redact
    except ImportError:
        return unavailable
    return available


def test_case_and_session_exact():
    g=Guard();raw='Username=Abelion'
    out=g.request({'messages':[{'role':'user','content':raw}]},session_id='a')['request']
    token=TOKEN.search(str(out))[0]
    assert g.output(token,session_id='a',platform='cli')==_expected_output('Abelion',MARKER)
    assert g.output(token.lower(),session_id='a',platform='cli')==MARKER
    assert g.output(token.upper(),session_id='a',platform='cli')==MARKER
    assert g.output(token,session_id='b',platform='cli')==MARKER
    assert g.output(token,session_id='a',platform='api')==_expected_output(token,MARKER)
    assert g.output(token,session_id='a',platform='whatsapp')==_expected_output(token,MARKER)
    typo=token[:-2]+('0' if token[-2]!='0' else '1')+'>'
    assert g.output(typo,session_id='a',platform='cli')==MARKER

def test_all_surfaces_and_no_mutation():
    g=Guard();v='aK9-xQ2_mP7.vZ4Lw8Yd3'
    r={'messages':[{'role':'assistant','tool_calls':[{'id':'keep','function':{'name':'keep','arguments':json.dumps({'openweather_api_key':v})}}]}], 'system':'/home/abelion/secret/project', 'headers':{'authorization':'Bearer '+v},'tools':[{'function':{'name':'keep','parameters':{'properties':{'hf_api_key':{'type':'string','default':v}}}}}]}
    before=copy.deepcopy(r);out=g.request(r,session_id='a')['request'];text=json.dumps(out)
    assert v not in text and '/home/abelion' not in text
    assert r==before and out['messages'][0]['tool_calls'][0]['id']=='keep'
    assert out['tools'][0]['function']['name']=='keep'
    assert v not in g.output('api_key='+v,session_id='a',platform='cli')

def test_tool_destinations_are_closed():
    g=Guard();s=g.session('a');p=g.remember(s,'/home/abelion/report.txt','PATH');secret=g.remember(s,'hunter2','SECRET')
    assert g.tool_request('read_file',{'path':p},session_id='a')['args']['path']=='/home/abelion/report.txt'
    for tool,args in [('terminal',{'command':'cat '+p}),('read_file',{'path':secret}),('send_message',{'message':p})]:
        new=g.tool_request(tool,args,session_id='a')['args'];assert g.pre_tool(new)['action']=='block'
    assert g.pre_tool({'path':p.lower()})['action']=='block'
    assert g.tool_request('read_file',{'path':p},session_id='b')['args']['path']==p

def test_capacity_no_raw_and_clear():
    g=Guard(max_entries=1);out=g.request({'a':'email=a@b.test\nphone 0812-3456-7890'},session_id='a')['request']
    assert 'a@b.test' not in str(out) and '0812-3456-7890' not in str(out)
    assert MARKER in str(out)
    g.close(session_id='a');assert not g.sessions
    assert 'secret' not in str(g.request({'content':'my secret'},session_id='')['request'])

def test_opaque_and_cycle_never_forwarded():
    g=Guard();a={};a['loop']=a;a['blob']=b'hunter2';out=g.request(a,session_id='a')['request'];assert 'hunter2' not in str(out)

def test_url_unchanged_path_hidden():
    g=Guard();s=g.session('a')
    assert g.text('https://example.test/home/public/docs',s)=='https://example.test/home/public/docs'
    assert '/home/abelion' not in g.text('/home/abelion/Documents/project',s)

def test_prefix_secret_and_indonesian_pii():
    g=Guard();s=g.session('a')
    for text in ['acme_secret_blob=Zk7Qm2Wp9Rt4Lx8vN5','phone 0812-3456-7890','card 4111 1111 1111 1111','NIK 3174051203990001','key ghp_Ab1Cd2Ef3Gh4Ij5Kl6Mn7Op8Qr9St0Uv1Wx2']:  # gitleaks:allow (synthetic privacy test canary)
        assert g.text(text,s)!=text

def test_review_partial_tail_and_short_values():
    for text in ['password=Ab$cd;efgh&ij(k)','password: pa(ss)word,xyz','DB_PASSWORD=ab{c}d[e]f<g>h','password: x<HG:aa:bb>LEAKME','password: <HG:aa:bb>x hunter2']:
        g=Guard();out=g.request({'m':text},session_id='a')['request']['m']
        for tail in ['efgh','word,xyz','{c}d','LEAKME','hunter2']:assert tail not in out
    g=Guard();g.request({'m':'username: a'},session_id='a')
    assert g.request({'m':'a cat sat'},session_id='a')['request']['m']=='a cat sat'

def test_review_kind_drift_and_bearer_userinfo():
    g=Guard();out=g.request({'m':'call 0812345678901'},session_id='a')['request']['m'];token=TOKEN.search(out)[0]
    g.request({'m':'password=0812345678901'},session_id='a')
    assert g.output(token,session_id='a',platform='cli')==_expected_output(token,MARKER)
    for text,raw in [('Authorization: Bearer abc.def.ghi-1234567890','abc.def.ghi-1234567890'),('mysql://root:pw123@host/db','pw123'),('ssh://user:pw@host','user:pw')]:
        assert raw not in g.request({'m':text},session_id='a')['request']['m']

def test_media_withheld_no_ocr_claim():
    g=Guard();out=g.request({'messages':[{'role':'user','content':[{'type':'image_url','image_url':{'url':'data:image/png;base64,1234567890123456'}}]}]},session_id='a')['request']
    assert 'data:image' not in str(out) and 'GUARD_WITHHELD_MEDIA' in str(out)

def test_bounded_redos():
    import time
    for text in ['a.'*20000+'@','a-'*20000+'@b','http://'*10000]:
        t=time.monotonic();Guard().request({'m':text},session_id='a');assert time.monotonic()-t<2

def test_scan_budget_before_work_and_short_flags():
    import time
    for text in ['http://'*16000,'password=a\n'*16000]:
        t=time.monotonic();out=Guard().request({'m':text},session_id='a');assert time.monotonic()-t<1
        assert text not in str(out)
    for text,raw in [('curl -u admin:pw123 http://h','admin:pw123'),('mysql -pSecret123 db','Secret123'),('/home/abelion/a b/c.txt','b/c.txt')]:  # gitleaks:allow (synthetic privacy test canary)
        assert raw not in str(Guard().request({'m':text},session_id='a'))

def test_dense_text_and_cumulative_payload_budget():
    import time
    for text in ['bearer '*18000,'basic x '*16000,'a@b.c '*16000]:
        t=time.monotonic();out=Guard().request({'m':text},session_id='a');assert time.monotonic()-t<1
        assert MARKER in str(out)
    request={'chunks':['plain '+str(i)+'a'*30000 for i in range(20)]}
    out=Guard().request(request,session_id='a')['request']
    assert MARKER in str(out) and request['chunks'][-1]!=MARKER


def test_required_oversize_denies_without_corrupting_request():
    import copy
    guard=Guard();request={'model':'test','messages':[{'role':'user','content':'a'*3000} for _ in range(1000)],'tools':[{'type':'function','function':{'name':'read_file'}}],'tool_choice':'auto'}
    before=copy.deepcopy(request)
    assert guard.required_policy('request',request=request,session_id='required')=={'allow':False,'reason':'capacity'}
    assert request==before


def test_required_control_secret_denies_but_content_masks():
    guard=Guard()
    assert guard.required_policy('request',request={'model':'test','extra_headers':{'Authorization':'Bearer opaque-secret-abcdefghijk'}},session_id='required')=={'allow':False}
    result=guard.required_policy('request',request={'model':'test','messages':[{'role':'user','content':'api_key=OpaqueZ9p4X6v8Q2'}]},session_id='required')  # gitleaks:allow (synthetic privacy test canary)
    assert result['allow'] is True
    assert 'OpaqueZ9p4X6v8Q2' not in str(result)  # gitleaks:allow (synthetic privacy test canary)


def test_required_capacity_recovery_is_new_session_not_eviction():
    guard=Guard(max_entries=1)
    first={'model':'test','messages':[{'role':'user','content':'api_key=FirstOpaqueX9t7a5v3'}]}  # gitleaks:allow (synthetic privacy test canary)
    second={'model':'test','messages':[{'role':'user','content':'password=SecondOpaqueX9t7a5v3'}]}  # gitleaks:allow (synthetic privacy test canary)
    assert guard.required_policy('request',request=first,session_id='A')['allow']
    assert guard.required_policy('request',request=second,session_id='A')['allow'] is False
    assert guard.required_policy('request',request=second,session_id='B')['allow']
    assert len(guard.sessions['A'].entries)==1


def test_cookie_source_material_denied_opaque_limit_explicit():
    cases=[{'extra_headers':{'Cookie':'sid=OpaqueCookieX9v7t5'}},
           {'messages':[{'content':'Set-Cookie: sid=OpaqueCookieX9v7t5; HttpOnly'}]},
           {'messages':[{'content':'{"localStorage":{"sid":"OpaqueCookieX9v7t5"}}'}]}]
    for request in cases:
        result=Guard().required_policy('request',request=request,session_id='cookies')
        assert result=={'allow':False,'reason':'session_material'}
    result=Guard().required_policy('request',request={'messages':[{'content':'OpaqueCookieX9v7t5'}]},session_id='opaque')
    assert result['allow'] and 'OpaqueCookieX9v7t5' in str(result)


def test_common_path_diagnostics_preserve_path_kind_without_space_leak():
    for text in ['open /home/abelion/a.py please','see /home/abelion/a.py, then fix it','cat /home/abelion/a.py && echo done','File: /home/abelion/a.py (12 lines)','/home/abelion/a.py:12: error here','path=/home/abelion/a.py ok']:
        g=Guard();result=g.request({'m':text},session_id='path')['request']['m']
        token=TOKEN.search(result)[0]
        assert g.sessions['path'].entries[token].kind=='PATH',text
        assert g.sessions['path'].entries[token].value=='/home/abelion/a.py',text
        assert g.tool_request('read_file',{'path':token},session_id='path')['args']['path']=='/home/abelion/a.py'
    result=Guard().request({'m':'/home/abelion/a b/c.txt'},session_id='ambiguous')['request']
    assert 'b/c.txt' not in str(result)


def test_required_denial_reasons_not_all_capacity():
    g=Guard()
    media={'messages':[{'content':[{'type':'image_url','image_url':{'url':'http://local.test/x.png'}}]}]}
    assert g.required_policy('request',request=media,session_id='A')['reason']=='media'
    assert g.required_policy('request',request={'m':object()},session_id='A')['reason']=='unsupported_content'
    foreign='<HG:'+'a'*24+':'+'b'*24+'>'
    assert g.required_policy('request',request={'m':foreign},session_id='A')['reason']=='unknown_placeholder'


def test_masked_delegate_handoff_is_denied_no_cross_session_restore():
    guard=Guard();token=guard.remember(guard.session('parent'),'/private/parent/file','PATH')
    assert guard.required_policy('tool',tool_name='delegate_task',args={'goal':'read '+token},session_id='parent')['allow'] is False
    result=guard.required_policy('request',request={'messages':[{'content':token}]},session_id='child')
    assert result=={'allow':False,'reason':'unknown_placeholder'}


def test_json_and_quoted_paths_keep_structure_and_diagnostics():
    samples=['{"status":"ok","path":"/home/abelion/a.py","content":"print(1)","lines":1}',
             '{"cwd":"/home/abelion/proj","output":"done","exit_code":0}',
             '{"files":["/home/abelion/a.py","/home/abelion/b.py"],"total":2}']
    for raw in samples:
        g=Guard();out=g.request({'m':raw},session_id='A')['request']['m']
        assert json.loads(out).keys()==json.loads(raw).keys()
        assert all(e.kind=='PATH' for e in g.sessions['A'].entries.values())
    for raw in ["open('/home/abelion/a.py')","cat '/home/abelion/a.py'",'[/home/abelion/a.py]','(/home/abelion/a.py)','File "/home/abelion/a.py", line 3, in module',"ENOENT open '/home/abelion/a.py'"]:
        g=Guard();out=g.request({'m':raw},session_id='A')['request']['m']
        assert all(e.kind=='PATH' for e in g.sessions['A'].entries.values()),raw
        assert len(out)>len(TOKEN.search(out)[0])


def test_cookie_docs_allowed_but_named_material_denied():
    g=Guard()
    docs={'messages':[{'role':'system','content':'Browser supports cookies, localStorage and storage_state. I like cookie recipes.'}], 'tools':[{'type':'function','function':{'name':'browser_exec','description':'Inspect cookies when allowed','parameters':{'type':'object','properties':{'cookies':{'type':'string','description':'cookie value'}}}}}]}
    assert g.required_policy('request',request=docs,session_id='A')['allow']
    for raw in ['{"cookies":[{"name":"a","value":"Zm9vYmFy"}]}','JSESSIONID=ABCD1234EFGH5678','Set-Cookie: sid=x']:
        assert not g.required_policy('request',request={'messages':[{'content':raw}]},session_id='A')['allow']


def test_cookie_schema_boundary_not_arbitrary_parameters():
    g=Guard()
    assert not g.session_material({'tools':[{'type':'function','function':{'name':'help','parameters':{'type':'object','properties':{'cookies':{'type':'array'}}}}}]})
    assert g.session_material({'parameters':{'cookies':[{'name':'sid','value':'opaque'}]}})
    assert not g.session_material({'tools':[{'type':'function','function':{'name':'help','parameters':{'type':'object','description':'Cookie: name=value'}}}]})


def test_ordinary_session_ids_and_schema_examples_not_material():
    g=Guard()
    for value in [{'session_id':'proc_1'},{'session_id':'proc_1','status':'running'},'my session_id: how do I fix']:
        assert not g.session_material(value)
    descriptions=['Pass session_id: the id','sid: string','refresh_token: optional','access_token=<token>',
                  'Cookie: name=value','Optional headers e.g. {"Cookie":"a=b"}',
                  'Returns {"cookies":[{"name":"...","value":"..."}]}']
    for text in descriptions:
        request={'tools':[{'type':'function','function':{'name':'example','description':text,'parameters':{'type':'object'}}}]}
        assert not g.session_material(request)
        assert Guard().required_policy('request',request=request,session_id='docs')['allow']
    for value in ['Cookie: a=b','Set-Cookie: s=x',{'headers':{'Cookie':'a=b'}},
                  {'cookies':[{'name':'a','value':'b'}]},'[{"cookies":[{"name":"a","value":"b"}]}]']:
        assert g.session_material(value)
