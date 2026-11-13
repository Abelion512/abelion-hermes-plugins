"""Independent producer collection through an injected authenticated READ transport.
No candidate-supplied context/digest is accepted and no candidate code runs.
"""
import base64
from urllib.parse import quote
from proof_context import normalize_context
from triage import collect

REPO='Abelion512/abelion-hermes-plugins'
ROOT='/repos/'+REPO

def collect_context(gh,pr_number,*,repo_id,bot_id,owner_id,bot_slug,request_comment_id):
    """Fetch full source/diff and reviewer snapshot, reject concurrent movement.

    Adapter must expose strict UTF-8 `raw=True` diff reads and complete pages.
    Token permissions, network limits and GET-only behavior belong to adapter.
    This function never dispatches a workflow or trusts an input context hash.
    """
    if type(pr_number) is not int or pr_number<=0:raise ValueError('invalid_pr')
    if type(repo_id) is not int or repo_id<=0:raise ValueError('invalid_repo_id')
    try:
        pr=gh.request(ROOT+'/pulls/'+str(pr_number))
        if pr['state']!='open' or pr.get('draft') is not False or pr['head']['repo']['id']!=repo_id:
            raise ValueError('producer_pr_not_eligible')
        head,base=pr['head']['sha'],pr['base']['sha']
        discussions,fingerprint,_=collect(gh,pr_number,bot_id,request_comment_id,owner_id,bot_slug)
        files=gh.pages(ROOT+'/pulls/'+str(pr_number)+'/files')
        if type(files) is not list or not 0<len(files)<=30:raise ValueError('producer_file_count')
        if type(pr.get('changed_files')) is not int or pr['changed_files']!=len(files):raise ValueError('producer_file_coverage_mismatch')
        paths=[];sources={}
        for f in files:
            path=f['filename'];status=f['status']
            if type(path) is not str or status not in ('added','modified'):raise ValueError('producer_source_status')
            if path in sources:raise ValueError('producer_duplicate_path')
            item=gh.request(ROOT+'/contents/'+quote(path,safe='/')+'?ref='+head)
            if item.get('encoding')!='base64' or item.get('type','file')!='file':raise ValueError('producer_source_encoding')
            encoded=item['content']
            if type(encoded) is not str:raise ValueError('producer_source_encoding')
            raw=base64.b64decode(''.join(encoded.split()),validate=True)
            if len(raw)>240000:raise ValueError('producer_source_limit')
            sources[path]=raw.decode('utf-8','strict')
            paths.append({'filename':path,'status':status})
        diff=gh.request(ROOT+'/compare/'+base+'...'+head,raw=True)
        if type(diff) is bytes:diff=diff.decode('utf-8','strict')
        if type(diff) is not str:raise ValueError('producer_diff_type')
        context=normalize_context({'pr':pr_number,'sha':head,'base':base,'paths':paths,'sources':sources,
            'diff':diff,'comments_fingerprint':fingerprint,
            'finding_ids':[str(d['kind'])+':'+str(d['id']) for d in discussions]})
        newest=gh.request(ROOT+'/pulls/'+str(pr_number))
        if (newest['head']['sha']!=head or newest['base']['sha']!=base or newest['state']!='open'
                or newest.get('draft') is not False or type(newest.get('changed_files')) is not int or newest.get('changed_files')!=len(files)):raise ValueError('producer_head_or_base_changed')
        _,latest_fingerprint,_=collect(gh,pr_number,bot_id,request_comment_id,owner_id,bot_slug)
        if latest_fingerprint!=fingerprint:raise ValueError('producer_comments_changed')
        return context
    except (KeyError,TypeError,AttributeError,UnicodeError) as exc:
        raise ValueError('malformed_producer_source') from exc
