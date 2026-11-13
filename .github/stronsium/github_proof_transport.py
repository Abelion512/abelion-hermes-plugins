"""GET-only proof transport. Credentials and archive-host policy are owner wiring.
No dispatch, writes, candidate execution, redirects with Authorization, or retries.
"""
import json
import urllib.request
import urllib.error
from urllib.parse import urlsplit, parse_qsl, urlencode, unquote
from proof_evidence import ProofVerifier, ProducerPolicy, MAX_BYTES, REPO

ROOT='/repos/'+REPO+'/'
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None

def unique(pairs):
    out={}
    for k,v in pairs:
        if k in out:raise ValueError('duplicate_api_key')
        out[k]=v
    return out

class GitHubProofTransport:
    def __init__(self,token_provider,*,archive_hosts=()):
        if not callable(token_provider):raise ValueError('authenticated_read_wiring_missing')
        if (type(archive_hosts) is not tuple or any(type(h) is not str or not h or '/' in h or ':' in h or '*' in h for h in archive_hosts)):
            raise ValueError('archive_host_policy_invalid')
        self.token_provider=token_provider
        self.archive_hosts=archive_hosts
        self.opener=urllib.request.build_opener(NoRedirect())
    def _api(self,path,*,raw=False):
        u=urlsplit(path)
        decoded=unquote(u.path)
        if (not path.startswith(ROOT) or u.scheme or u.netloc or u.fragment
                or any(p in ('.','..') for p in decoded.split('/')) or '\\' in decoded
                or any(ord(c)<32 for c in path+decoded)):
            raise ValueError('api_path_outside_repository')
        token=self.token_provider()
        if type(token) is not str or not token or any(c in token for c in '\r\n'):
            raise ValueError('authenticated_read_wiring_missing')
        return urllib.request.Request('https://api.github.com'+path,method='GET',headers={
            'Authorization':'Bearer '+token,'Accept':'application/vnd.github.diff' if raw else 'application/vnd.github+json',
            'X-GitHub-Api-Version':'2022-11-28','User-Agent':'Stronsium-Proof-Read/1'})
    @staticmethod
    def _read(response,limit):
        data=response.read(limit+1)
        if type(data) is not bytes or len(data)>limit:raise ValueError('response_limit')
        return data
    def request(self,path,method='GET',body=None,raw=False):
        if method!='GET' or body is not None:raise ValueError('proof_transport_read_only')
        req=self._api(path,raw=raw)
        with self.opener.open(req,timeout=30) as r:
            if r.status!=200:raise ValueError('unexpected_api_status')
            data=self._read(r,2_000_000)
        text=data.decode('utf-8','strict')
        if raw:return text
        return json.loads(text,object_pairs_hook=unique,parse_constant=lambda v:(_ for _ in ()).throw(ValueError('invalid_api_number')))
    def pages(self,path,result_key=None):
        u=urlsplit(path);query=parse_qsl(u.query,keep_blank_values=True)
        if any(k in ('page','per_page') for k,v in query):raise ValueError('caller_pagination_denied')
        out=[];seen=set();expected_total=None
        for page in range(1,101):
            p=u.path+'?'+urlencode(query+[('per_page','100'),('page',str(page))])
            value=self.request(p)
            items=value.get(result_key) if result_key and type(value) is dict else value
            if type(items) is not list or len(items)>100:raise ValueError('invalid_api_page')
            if result_key:
                total=value.get('total_count')
                if type(total) is not int or total<0:raise ValueError('pagination_total_missing')
                if expected_total is None:expected_total=total
                if total!=expected_total:raise ValueError('pagination_total_changed')
            for item in items:
                if type(item) is dict and 'id' in item:
                    ident=item['id']
                    if type(ident) is not int or ident<=0 or ident in seen:raise ValueError('pagination_duplicate_or_invalid_id')
                    seen.add(ident)
            out.extend(items)
            if len(items)<100:
                if expected_total is not None and len(out)!=expected_total:raise ValueError('pagination_incomplete_total')
                return out
        raise ValueError('pagination_limit_not_complete')
    def artifact_zip(self,artifact_id):
        if type(artifact_id) is not int or artifact_id<=0:raise ValueError('invalid_artifact_id')
        req=self._api(ROOT+'actions/artifacts/'+str(artifact_id)+'/zip')
        try:
            with self.opener.open(req,timeout=30):
                raise ValueError('expected_archive_redirect')
        except urllib.error.HTTPError as e:
            if e.code!=302:raise
            location=e.headers.get('Location','')
            e.close()
        u=urlsplit(location)
        if (u.scheme!='https' or u.hostname not in self.archive_hosts or u.username or u.password
                or u.port not in (None,443) or u.fragment or '\\' in location
                or any(ord(c)<32 for c in location)):
            raise ValueError('unapproved_archive_destination')
        # A new Request with NO Authorization; NoRedirect also applies here.
        external=urllib.request.Request(location,method='GET',headers={'User-Agent':'Stronsium-Proof-Read/1'})
        with self.opener.open(external,timeout=30) as r:
            if r.status!=200:raise ValueError('unexpected_archive_status')
            return self._read(r,MAX_BYTES)

class SelectedArtifactProof:
    """Application selects immutable IDs. PR text/config cannot choose them."""
    def __init__(self,policy,transport,*,run_id,attempt,artifact_id):
        if type(policy) is not ProducerPolicy or type(transport) is not GitHubProofTransport:
            raise ValueError('proof_application_wiring_missing')
        if any(type(x) is not int or x<=0 for x in (run_id,attempt,artifact_id)):
            raise ValueError('invalid_selected_proof')
        self.policy=policy;self.transport=transport
        self.run_id=run_id;self.attempt=attempt;self.artifact_id=artifact_id
    def __call__(self,context):
        # Verify again on every invocation, including the final Consumer gate.
        raw=self.transport.artifact_zip(self.artifact_id)
        return ProofVerifier(self.policy,self.transport.request).verify(raw,context,
            run_id=self.run_id,attempt=self.attempt,artifact_id=self.artifact_id)
