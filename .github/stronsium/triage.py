"""Read all PR review discussions as untrusted data, without executing them."""
import hashlib,json,re
from proof_evidence import REPO
MARK='<!-- abelink-review:v1 -->'  # review marker; must equal the worker's marker
MAX_COMMENT_CHARS=60000

def collect(gh,pr,bot_id,request_comment_id,owner_id=None,bot_slug=None):
 root='/repos/'+REPO
 conversations=gh.pages(root+'/issues/'+str(pr)+'/comments')
 inline=gh.pages(root+'/pulls/'+str(pr)+'/comments')
 reviews=gh.pages(root+'/pulls/'+str(pr)+'/reviews')
 prior=[];comments=[]
 for kind,rows in [('conversation',conversations),('inline',inline),('review',reviews)]:
  for c in rows:
   body=c.get('body') or ''
   if kind=='conversation' and c['user']['id']==bot_id and MARK in body:
    prior.append(c);continue
   # Agent's replies don't become new instructions and the owner's command isn't a finding.
   if c['user']['id']==bot_id or kind=='conversation' and c['id']==request_comment_id:continue
   if not body:continue
   if kind=='conversation' and c['user']['id']==owner_id and bot_slug and re.search(r'(?<![\w-])@'+re.escape(bot_slug)+r'(?:\[bot\])?(?![\w-])',body,re.I):continue
   comments.append({'kind':kind,'id':c['id'],'author_id':c['user']['id'],'body':body,'path':c.get('path'),'line':c.get('line'),'commit_id':c.get('commit_id'),'updated_at':c.get('updated_at'),'html_url':c.get('html_url')})
 comments.sort(key=lambda c:(c['kind'],c['id']))
 serial=json.dumps(comments,sort_keys=True,ensure_ascii=False)
 if len(comments)>50 or len(serial)>MAX_COMMENT_CHARS:raise ValueError('review_comments_limit')
 fingerprint=hashlib.sha256(serial.encode()).hexdigest()
 prior.sort(key=lambda c:(c.get('updated_at',''),c['id']),reverse=True)
 return comments,fingerprint,prior[0] if prior else None

def validate_triage(entries,comments):
 valid={(c['kind'],c['id']) for c in comments}
 seen=set()
 if not isinstance(entries,list) or len(entries)!=len(comments):raise ValueError('missing_comment_triage')
 for e in entries:
  key=(e.get('kind'),e.get('id'))
  if key not in valid or key in seen:raise ValueError('invalid_comment_triage')
  seen.add(key)
  if e.get('status') not in ['valid','rejected','unproven']:raise ValueError('invalid_triage_status')
  reason=e.get('reason')
  if not isinstance(reason,str) or not 1<=len(reason)<=1000:raise ValueError('invalid_triage_reason')
 return entries
