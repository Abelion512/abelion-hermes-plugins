import sys,json,hashlib,copy,collections
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from pii_mask_abelion.guard import Guard,MARKER
from pii_mask_abelion.pii_middleware import mask_content,pii_middleware
path=Path(sys.argv[1]) if len(sys.argv)>1 else Path('/tmp/chatgpt-exact-pack/abelion_security_test_pack/abelion_security_test_cases.jsonl')
rows=[json.loads(x) for x in path.read_text().splitlines()];out=[]
for c in rows:
 rec={k:c[k] for k in ['id','plugin','category','severity']};e=c['expected'];i=c['input']
 if c['plugin'].startswith('guard.'):
  rec.update(status='retired_target',reason='Targets removed Shield contract, not automatically equivalent to native Hermes. No tool dispatched.');out.append(rec);continue
 try:
  if c['plugin']=='mask':
   if isinstance(i,dict):
    orig=copy.deepcopy(i);v=pii_middleware(i);v=v['request'] if v else i;actual=json.dumps(v);count=int(v!=i);source_ok=orig==i
    active=Guard().required_policy('request',request=dict({'model':'synthetic'},**copy.deepcopy(i)),session_id=c['id'])
    active_text=json.dumps(active.get('request')) if active.get('allow') else '[DENIED]'
   else:
    actual,count=mask_content(i);source_ok=True
    active=Guard().required_policy('request',request={'model':'synthetic','messages':[{'role':'user','content':i}]},session_id=c['id'])
    active_text=json.dumps(active.get('request')) if active.get('allow') else '[DENIED]'
   bad=[x for x in e.get('must_not_contain',[]) if x in actual]
   ok=not bad and count>=e.get('minimum_replacements',0) and source_ok
   if e.get('must_equal_input') or e.get('outcome')=='must_leave_benign_text_unchanged':ok=ok and actual==(json.dumps(i) if isinstance(i,dict) else i)
   active_bad=[x for x in e.get('must_not_contain',[]) if x in active_text]
   rec.update(status='pass' if ok else 'fail',actual=actual,active_guard_canary_absent=not active_bad,active_guard_allowed=active.get('allow'),remaining_sentinels=bad)
   if e.get('outcome')=='must_mask_internal_sensitive_value':rec['policy_note']='INTERNAL prose-wide masking is a proposed stronger policy, not a configured current contract.'
  else:
   g=Guard();actual=g.output(i,session_id=c['id'],platform='api');bad=[x for x in e.get('must_not_contain',[]) if x in actual]
   ok=not bad
   if e.get('must_not_introduce_error'):ok=ok and actual not in [MARKER] and not actual.startswith('[OUTPUT_WITHHELD')
   rec.update(status='pass' if ok else 'fail',actual=actual,remaining_sentinels=bad)
 except Exception as ex:rec.update(status='error',reason=type(ex).__name__+': '+str(ex))
 out.append(rec)
summary={'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'total':len(out),'status':dict(collections.Counter(x['status'] for x in out)),'by_plugin':{p:dict(collections.Counter(x['status'] for x in out if x['plugin']==p)) for p in sorted(set(x['plugin'] for x in out))},'rows':out}
Path('/tmp/exact-matrix-results.json').write_text(json.dumps(summary,indent=2));print(json.dumps({k:v for k,v in summary.items() if k!='rows'},indent=2))
for x in out:
 if x['status'] in ['fail','error']:print(x['id'],x['category'],x.get('remaining_sentinels'),x.get('active_guard_canary_absent'),x.get('actual',x.get('reason'))[:150])
