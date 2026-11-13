"""Runs inside the pinned default-branch producer workflow (pull_request_target; issue_comment also supported). GET-only. Never checks out or runs PR code.
The context digest is computed HERE from independently collected data; no digest or context is an input.
Inputs: PR number and triggering comment id (workflow event fields, validated as digits). Output: proof.json plus
a one-line digest file used only to NAME the artifact (the consumer re-derives the name from its own context)."""
import io,json,os,pathlib,re,sys,zipfile
from github_proof_transport import GitHubProofTransport
from producer_context import collect_context
from proof_closure import local_closure_digest
from proof_context import context_digest
from proof_producer import ProofProducer

def run(pr_number,comment_id,out,env,identity,policy,program,transport,semantic=None):
    for k in ('GITHUB_RUN_ID','GITHUB_RUN_ATTEMPT'):
        if not env.get(k,'').isdigit():raise ValueError('runner_identity_missing')
    head_sha=env.get('GITHUB_SHA','')
    if not re.fullmatch('[a-f0-9]{40}',head_sha):raise ValueError('runner_head_sha_missing')
    # The closure pin is computed HERE from the default-branch checkout; produce()
    # refuses when it does not match the pinned policy digest.
    closure=local_closure_digest(env.get('GITHUB_WORKSPACE',''))
    if policy is None or program is None:raise ValueError('producer_policy_unset')
    if env.get('GITHUB_EVENT_NAME')!=policy.event or policy.event not in ('issue_comment','pull_request_target'):raise ValueError('wrong_event')
    if type(pr_number) is not int or not 0<pr_number<=999999999:raise ValueError('invalid_pr')
    # pull_request_target has no request comment: id 0 (nothing to exclude). issue_comment needs a real id.
    if type(comment_id) is not int or not 0<=comment_id<=9007199254740991 or (comment_id==0 and policy.event=='issue_comment'):raise ValueError('invalid_comment')
    if out!='proof.json':raise ValueError('invalid_output_path')
    ident=dict(identity);ident['request_comment_id']=comment_id
    context=collect_context(transport,pr_number,**ident)
    digest=context_digest(context)
    producer=ProofProducer(policy,program,semantic)
    archive=producer.produce(context,run_id=int(env['GITHUB_RUN_ID']),attempt=int(env['GITHUB_RUN_ATTEMPT']),
        head_sha=head_sha,closure_sha256=closure)
    latest=collect_context(transport,pr_number,**ident)
    if context_digest(latest)!=digest:raise ValueError('producer_snapshot_changed_during_checks')
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        if z.namelist()!=['proof.json']:raise ValueError('producer_archive_shape')
        body=z.read('proof.json')
    pathlib.Path(out).write_bytes(body)
    pathlib.Path('digest.txt').write_text(digest+'\n')
    return digest

def main(argv,env):
    import producer_identity as I   # derived from the pinned commit; refuses off-default-branch
    if len(argv)!=4 or not re.fullmatch('[0-9]{1,9}',argv[1]) or not re.fullmatch('[0-9]{1,16}',argv[2]):raise ValueError('usage')
    token=env.get('GH_TOKEN','')
    policy,program=I.load(env)
    d=run(int(argv[1]),int(argv[2]),argv[3],env,I.IDENTITY,policy,program,GitHubProofTransport(lambda:token),I.SEMANTIC)
    gh_out=env.get('GITHUB_OUTPUT')
    if gh_out:
        with open(gh_out,'a') as f:f.write('digest='+d+'\n')

if __name__=='__main__':main(sys.argv,dict(os.environ))
