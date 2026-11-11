"""Canonical context v1: strict strings, stable ordering, no newline translation."""
import copy
import hashlib
import json
import re

KEYS={'pr','sha','base','paths','sources','diff','comments_fingerprint','finding_ids'}
MAX_CONTEXT=240000
SHA=re.compile('[a-f0-9]{40}')

def normalize_context(value):
    try:
        if type(value) is not dict or set(value)!=KEYS:
            raise ValueError('context_schema')
        c=copy.deepcopy(value)
        if type(c['pr']) is not int or not 0<c['pr']<=9007199254740991:
            raise ValueError('context_pr')
        if any(type(c[k]) is not str or not SHA.fullmatch(c[k]) for k in ('sha','base')):
            raise ValueError('context_sha')
        if type(c['paths']) is not list or not c['paths'] or len(c['paths'])>30:
            raise ValueError('context_paths')
        for f in c['paths']:
            if type(f) is not dict or set(f)!={'filename','status'}:
                raise ValueError('context_path_schema')
            path=f['filename']
            if (type(path) is not str or not path or path.startswith('/') or '\\' in path
                    or any(part in ('','.','..') for part in path.split('/'))
                    or any(ord(ch)<32 for ch in path) or f['status'] not in ('added','modified')):
                raise ValueError('context_path')
        names=[f['filename'] for f in c['paths']]
        if len(names)!=len(set(names)) or type(c['sources']) is not dict or set(c['sources'])!=set(names):
            raise ValueError('context_source_coverage')
        if any(type(v) is not str for v in c['sources'].values()):
            raise ValueError('context_source_type')
        if any(type(c[k]) is not str or not c[k] for k in ('diff','comments_fingerprint')):
            raise ValueError('context_text')
        ids=c['finding_ids']
        if type(ids) is not list or any(type(i) is not str or not i for i in ids) or len(ids)!=len(set(ids)):
            raise ValueError('context_finding_ids')
        c['paths'].sort(key=lambda f:f['filename'])
        c['finding_ids'].sort()
        raw=json.dumps(c,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8','strict')
        if len(raw)>MAX_CONTEXT:raise ValueError('context_limit')
        return c
    except (TypeError,KeyError,UnicodeError,RecursionError) as exc:
        raise ValueError('malformed_context') from exc

def canonical_bytes(context):
    return json.dumps(normalize_context(context),sort_keys=True,separators=(',',':'),
                      ensure_ascii=False,allow_nan=False).encode('utf-8','strict')

def context_digest(context):
    return hashlib.sha256(canonical_bytes(context)).hexdigest()
