"""Runs inside the pinned producer workflow. GET-only. Never checks out or runs PR code.
Identity constants come from producer_identity.py in the pinned commit, never workflow inputs.
"""
import io,json,os,pathlib,re,sys,zipfile
from github_proof_transport import GitHubProofTransport
from proof_closure import local_closure_digest
from proof_producer import FrozenProgram,ProofProducer,collect_and_produce
from proof_evidence import ProducerPolicy

def run(pr_number,digest,out,env,identity,policy,program,transport):
    for k in ('GITHUB_RUN_ID','GITHUB_RUN_ATTEMPT'):
        if not env.get(k,'').isdigit():raise ValueError('runner_identity_missing')
    head_sha=env.get('GITHUB_SHA','')
    if not re.fullmatch('[a-f0-9]{40}',head_sha):raise ValueError('runner_head_sha_missing')
    closure=local_closure_digest(env.get('GITHUB_WORKSPACE',''))
    if type(pr_number) is not int or not 0<pr_number<=999999999:raise ValueError('invalid_pr')
    if type(digest) is not str or not re.fullmatch('[a-f0-9]{64}',digest):raise ValueError('invalid_digest')
    if type(out) is not str or out!='proof.json':raise ValueError('invalid_output_path')
    archive=collect_and_produce(ProofProducer(policy,program),transport,pr_number,collector_identity=identity,
        expected_context_digest=digest,run_id=int(env['GITHUB_RUN_ID']),attempt=int(env['GITHUB_RUN_ATTEMPT']),
        head_sha=head_sha,closure_sha256=closure)
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        names=z.namelist()
        if names!=['proof.json']:raise ValueError('producer_archive_shape')
        body=z.read('proof.json')
    pathlib.Path(out).write_bytes(body)  # upload-artifact zips it; layout stays one proof.json entry

def main(argv,env):
    import producer_identity as I   # IDENTITY, POLICY, PROGRAM; unset values fail closed
    if len(argv)!=4 or not re.fullmatch('[0-9]{1,9}',argv[1]):raise ValueError('usage')
    token=env.get('GH_TOKEN','')
    transport=GitHubProofTransport(lambda:token)
    policy,program=I.load(env)   # derived from the pinned commit; refuses off-default-branch or unset pins
    run(int(argv[1]),argv[2],argv[3],env,I.IDENTITY,policy,program,transport)

if __name__=='__main__':main(sys.argv,dict(os.environ))
