"""Session-local text privacy guard. No network, disk mapping, or credential verification.

Native prefix rules are consumed from Hermes at runtime (MIT). Field-name detection
builds on this plugin's existing rules. A match is a risk signal, not format validation.
"""
from __future__ import annotations
import json
import math
import re
import secrets
import threading
import time
from dataclasses import dataclass, field
from urllib.parse import unquote
from . import _credentials as cred

TOKEN = re.compile(r'<HG:[0-9a-f]{24}:[0-9a-f]{24}>')
EMAIL = re.compile(r'(?<![\w.+-])[\w.+-]{1,64}@[A-Za-z0-9-]{1,63}(?:\.[A-Za-z0-9-]{1,63}){1,8}')
PHONE = re.compile(r'(?<![\w\d])(?:\+62|62|08)[\d -]{7,16}\d(?!\d)')
NUMBER = re.compile(r'(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)')
PATH = re.compile(r'(?<![\w:/])(?:/(?!/)[A-Za-z0-9_.-]+/|~/|[A-Za-z]:\\)[^\s"\'<>;,\]\[(){}]+')
URL = re.compile(r'\b[a-z][a-z0-9+.-]{0,31}://[^\s<>"\']+',re.I)
PEM = re.compile(r'-----BEGIN [A-Z0-9 ]*PRIVATE KEY(?: BLOCK)?-----[\s\S]*?(?:-----END [A-Z0-9 ]*PRIVATE KEY(?: BLOCK)?-----|\Z)')
LABEL = re.compile(r'(?i)\b(?:username|user_name|email|phone|address|alamat|nik|ktp|npwp)\b')
ASSIGN = re.compile(r'(?P<name>[A-Za-z][A-Za-z0-9_.%\-]{1,100})(?P<sep>["\']?\??[ \t]*(?:[:=]|%3[DdAa]|\t)[ \t]*)(?P<value>"(?:\\.|[^"\n])*"|\'(?:\\.|[^\'\n])*\'|[^\s"\',;&{}\[\]()]+)')
STRUCTURE = frozenset({'role','type','id','name','model','tool_call_id','call_id','mime_type','media_type','tool_choice','finish_reason','continuationToken'})
VALUE_KEYS = {'default','example','examples','const','value'}
AUTH_KEYS = frozenset({'authorization', 'proxy-authorization'})
MARKER = '[GUARD_WITHHELD]'
JWT_MATERIAL = re.compile(r'\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}(?:\.[A-Za-z0-9_-]+)?')
COOKIE_HEADER = re.compile(r'(?im)^(?:Cookie|Set-Cookie)\s*:\s*[^\r\n]*[^\s=;]+=[^\s;]+')
SESSION_ASSIGN = re.compile(r'(?im)^\s*(?:JSESSIONID|sessionid)\s*=\s*[^\s]+\s*$')


@dataclass(repr=False)
class Entry:
    value: str
    kind: str

@dataclass(repr=False)
class Session:
    nonce: str = field(default_factory=lambda: secrets.token_hex(12))
    entries: dict = field(default_factory=dict)
    reverse: dict = field(default_factory=dict)
    touched: float = field(default_factory=time.monotonic)
    size: int = 0

class Guard:
    """Bounded memory only. Expiry loses restoration, never forwards a forgotten map."""
    def __init__(self, max_sessions=64, max_entries=4096, max_bytes=2_000_000, ttl=3600):
        values=(max_sessions,max_entries,max_bytes)
        if any(type(v) is not int or v <= 0 for v in values):
            raise ValueError('capacity limits must be positive integers')
        if type(ttl) not in (int,float) or not math.isfinite(ttl) or ttl <= 0:
            raise ValueError('ttl must be positive and finite')
        self.sessions = {}
        self.lock = threading.RLock()
        self.limits = max_sessions,max_entries,max_bytes,ttl

    def session(self, sid):
        if not isinstance(sid,str) or not sid:
            raise ValueError('session identity required')
        now=time.monotonic()
        for key,s in list(self.sessions.items()):
            if now-s.touched > self.limits[3]: self.sessions.pop(key,None)
        if sid not in self.sessions:
            if len(self.sessions)>=self.limits[0]: raise ValueError('session capacity')
            self.sessions[sid]=Session()
        s=self.sessions[sid]; s.touched=now
        return s

    def remember(self,s,value,kind):
        key=value
        if key in s.reverse:
            token=s.reverse[key]
            if kind=='SECRET':s.entries[token].kind='SECRET'
            return token
        size=len(value.encode('utf-8'))
        if len(s.entries)>=self.limits[1] or s.size+size>self.limits[2]:
            return MARKER
        token=f'<HG:{s.nonce}:{secrets.token_hex(12)}>'
        while token in s.entries: token=f'<HG:{s.nonce}:{secrets.token_hex(12)}>'
        s.entries[token]=Entry(value,kind);s.reverse[key]=token;s.size+=size
        return token

    def spans(self,text):
        if len(text)>131_072:return [(0,len(text),'SECRET')]
        spans=[]
        def add(a,b,kind):
            if a<b: spans.append((a,b,kind))
        for pat in (cred.TOKEN_SHAPES,cred.TELEGRAM_TOKEN,cred.DISCORD_TOKEN,PEM):
            for m in pat.finditer(text): add(*m.span(),'SECRET')
        # Hermes' native fixed-prefix detector: complete span, never its partial display mask.
        try:
            from agent.redact import _PREFIX_RE
            for m in _PREFIX_RE.finditer(text): add(*m.span(),'SECRET')
        except ImportError: pass
        for m in re.finditer(r'--(?P<name>[A-Za-z][A-Za-z0-9_.-]{1,100})[ =](?P<value>"[^"\n]*"|\'[^\'\n]*\'|[^\s"\',;&<>{}\[\]()]+)',text):
            if cred.classify_field(m["name"].lstrip("-")):
                a,b=m.span("value");v=m["value"]
                if v[:1] in ("\"", "'"):a+=1;b-=1
                add(a,b,"SECRET")
        # Match only field heads first. Greedy value matching on rejected URL
        # heads used to rescan the whole suffix once per `http:` (quadratic).
        heads=list(re.finditer(r'(?P<name>[A-Za-z][A-Za-z0-9_.%\-]{1,100})(?P<sep>["\']?\??[ \t]*(?:[:=]|%3[DdAa]|\t)[ \t]*)',text))
        if len(heads)>512:return [(0,len(text),'SECRET')]
        for m in heads:
            name=unquote(unquote(m['name'])); kind=cred.classify_field(name)
            auth=name.lower() in AUTH_KEYS
            if auth:kind='SECRET'
            if not kind and re.search(r'(?i)(?:secret|credential)[_.-](?:blob|data|payload)$',name):kind='SECRET'
            if not kind and LABEL.fullmatch(name):kind='PII'
            if name.lower() in {'mongodb_uri','database_url','redis_url','connection_string'}:kind='SECRET'
            if not kind:continue
            a=m.end();end=text.find('\n',a);end=len(text) if end<0 else end
            v=text[a:end]
            if not v:continue
            if v[:1] in ('"',"'"):
                quote=v[0];i=1
                while i<len(v):
                    if v[i]=='\\':i+=2;continue
                    if v[i]==quote:break
                    i+=1
                a+=1;b=m.end()+i;v=text[a:b]
            else:
                b=end
                # Reference exclusions apply only to an entire scalar, never
                # a password prefix. Ambiguous punctuation stays hidden.
                scalar=v.split()[0] if v.split() else ''
                if not auth and (scalar=='$' or scalar.startswith('${') or scalar.startswith('<your-')):continue
                if not auth and (scalar=='token,' or scalar=='token)'):continue
                if not auth and v.strip().lower() in cred._CODE_WORDS:continue
                if not auth and cred._looks_like_reference(v.strip()) and '<HG:' not in v:continue
                if not auth and (cred._DOTTED.fullmatch(v.strip()) or cred._SNAKE.fullmatch(v.strip())) and not any(c.isdigit() for c in v):continue
                if v.endswith('.') and LABEL.fullmatch(name):b-=1
            if not v or (not auth and cred._looks_like_reference(v)):continue
            if kind=='PII' and name.lower()=='email' and not EMAIL.fullmatch(text[a:b]):kind='SECRET'
            add(a,b,kind)
        for m in re.finditer(r'(?i)(?:\bcurl\s+[^\n]*?-u\s+|\bmysql\s+[^\n]*?-p)([^\s]+)',text):add(*m.span(1),'SECRET')
        for m in re.finditer(r'(?i)\b(?:authorization\s*:\s*)?(?:bearer|basic)\s+([^\s\"\']+)',text): add(*m.span(1),'SECRET')
        for m in COOKIE_HEADER.finditer(text):add(*m.span(),'SECRET')
        for m in URL.finditer(text):
            at=m[0].rfind('@')
            if at>=0:
                start=m.start()+m[0].find('://')+3
                add(start,m.start()+at,'SECRET')
        for pat,kind in [(EMAIL,'PII'),(PHONE,'PII'),(NUMBER,'PII')]:
            if pat is EMAIL and '@' not in text:continue
            for m in pat.finditer(text): add(*m.span(),kind)
        urls=[m.span() for m in URL.finditer(text)]
        if len(urls)>256:return [(0,len(text),'SECRET')]
        for m in PATH.finditer(text):
            if not any(a<=m.start()<b for a,b in urls):
                end=text.find('\n',m.end());end=len(text) if end<0 else end
                tail=text[m.end():end]
                # Recognizable prose/shell/diagnostic delimiters are not a spaced filename.
                # Ambiguous unquoted whitespace paths remain withheld as one secret span.
                prose = re.match(r"\s*(?:please\b|then\b|and\b|ok\b|&&|\|\||[,(;\"\')\]{}]|<HG:)",tail)
                diagnostic=re.search(r':\d+(?::\d+)?(?::)?$',m[0])
                if tail.strip() and not prose and not diagnostic:
                    add(m.start(),end,'SECRET')
                else:
                    path_end=m.end()
                    if diagnostic:path_end=m.start()+diagnostic.start()
                    add(m.start(),path_end,'PATH')
        # Merge overlapping detections, but do not merge adjacent independent values.
        merged=[]
        for a,b,k in sorted(spans):
            if merged and a<merged[-1][1]:
                x,y,old=merged[-1];merged[-1]=(x,max(y,b),'SECRET' if 'SECRET' in (old,k) else old)
            else: merged.append((a,b,k))
        return merged

    def text(self,text,s):
        # Exact registered literals are masked even when the surrounding label is absent.
        # Placeholder-looking user input never creates a mapping.
        if len(text)>131_072:return MARKER
        low=text.lower()
        if text.count('@')>256 or low.count('bearer')+low.count('basic')>256:return MARKER
        if re.search(r'<HG:',text,re.I) and any(m[0] not in s.entries for m in TOKEN.finditer(text)):
            return MARKER
        if re.search(r'<HG:',TOKEN.sub('',text),re.I):return MARKER
        protected=[]
        for m in TOKEN.finditer(text): protected.append(m.span())
        scan=TOKEN.sub(lambda m:' '*len(m[0]) if m[0] in s.entries else m[0],text)
        spans=self.spans(scan)
        if len(spans)>512:return MARKER
        entries=list(s.entries.values())
        if len(entries)*len(text)>32_000_000:return MARKER
        for entry in entries:
            if len(entry.value)<4:continue
            start=0
            while entry.value and (i:=text.find(entry.value,start))>=0:
                end=i+len(entry.value)
                left=i==0 or not (text[i-1].isalnum() or text[i-1]=='_')
                right=end==len(text) or not (text[end].isalnum() or text[end]=='_')
                if left and right:spans.append((i,end,entry.kind))
                start=end
        clean=[]
        for a,b,k in sorted(spans,key=lambda t:(t[0],-(t[1]-t[0]))):
            if any(a==x and b==y and text[x:y] in s.entries for x,y in protected):continue
            if clean and a<clean[-1][1]:
                x,y,old=clean[-1];clean[-1]=(x,max(y,b),'SECRET' if 'SECRET' in (old,k) else old)
            else:clean.append((a,b,k))
        for a,b,k in reversed(clean):text=text[:a]+self.remember(s,text[a:b],k)+text[b:]
        return text

    def walk(self,obj,s,key='',depth=0):
        if depth>64:return MARKER
        if isinstance(obj,str):
            self.remaining-=len(obj)
            if self.remaining<0:return MARKER
            if key in {'image_url','data','b64_json','file_data','audio','bytes','signature','thoughtSignature','encrypted_content'} or obj.startswith('data:'):return MARKER
            if key in STRUCTURE:
                if self.spans(obj):return MARKER
                return obj
            # Credential headers are secrets even without a scheme or with a
            # reference-looking value. Required controls_changed denies header
            # rewriting rather than silently changing transport controls.
            if key.lower() in AUTH_KEYS:
                if obj in s.entries or not obj:return obj
                return self.remember(s,obj,'SECRET')
            # JSON text is still content. Walk decoded containers using the same
            # bounded policy as real objects, including name/value indirection.
            # Preserve benign JSON byte-for-byte, including whitespace.
            if obj.lstrip().startswith(('{','[')):
                try:
                    parsed=json.loads(obj)
                except (ValueError,TypeError,RecursionError):
                    parsed=None
                if isinstance(parsed,(dict,list)):
                    masked=self.walk(parsed,s,key,depth+1)
                    if masked != parsed:return json.dumps(masked,ensure_ascii=False)
            if key=='arguments':
                try:return json.dumps(self.walk(json.loads(obj),s,depth=depth+1),ensure_ascii=False)
                except (ValueError,TypeError):return self.text(obj,s)
            if (kind:=cred.classify_field(key)) or LABEL.fullmatch(key) or key.lower() in {'mongodb_uri','database_url','redis_url','connection_string'}:
                if obj in s.entries:return obj
                if obj and not cred._looks_like_reference(obj):return self.remember(s,obj,kind or ('SECRET' if key.lower() in {'mongodb_uri','database_url','redis_url','connection_string'} else 'PII'))
            return self.text(obj,s)
        if isinstance(obj,dict):
            if any(not isinstance(k,str) or self.spans(k) for k in obj):
                return MARKER
            if obj.get('type') in {'image_url','input_image','image','audio','input_audio','file','input_file'}:
                return {'type':'text','text':'[GUARD_WITHHELD_MEDIA: cover sensitive content locally]'}
            pair=obj.get('name')
            return {k:self.walk(v,s,pair if k=='value' and isinstance(pair,str) and (cred.classify_field(pair) or pair.lower() in AUTH_KEYS) else key if k in VALUE_KEYS and cred.classify_field(key) else k,depth+1) for k,v in obj.items() if isinstance(k,str)}
        if isinstance(obj,(list,tuple)):return [self.walk(v,s,key,depth+1) for v in obj]
        if obj is None or isinstance(obj,(bool,int,float)):return obj
        return MARKER  # SDK objects and bytes are never silently forwarded.

    def request(self,request,session_id='',**kwargs):
        with self.lock:
            try:
                s=self.session(session_id)
                self.remaining=262_144
                return {'request':self.walk(request,s)}
            except Exception:
                # Do not raise into Hermes' skip-and-send-original request handler.
                return {'request':self.withheld_request(request)}

    @staticmethod
    def withheld_request(request):
        return {'model':request.get('model','') if isinstance(request,dict) else '',
                'messages':[{'role':'user','content':MARKER}], 'stream':False}

    def required_policy(self,phase,**payload):
        if phase=='request':
            try:
                with self.lock:
                    request=payload['request']
                    if not isinstance(request,dict) or not request or ('messages' in request and (not isinstance(request['messages'],list) or not request['messages'])):
                        return {'allow':False,'reason':'invalid_request'}
                    if 'model' in request and (not isinstance(request['model'],str) or not request['model'].strip()):
                        return {'allow':False,'reason':'invalid_model'}
                    # Required mode never truncates a request or corrupts controls on
                    # budget overflow. JSON-only payload, bounded before walking.
                    raw=json.dumps(request,ensure_ascii=False,allow_nan=False)
                    if self.session_material(request):return {'allow':False,'reason':'session_material'}
                    if len(raw.encode('utf-8'))>2_097_152:return {'allow':False,'reason':'capacity'}
                    self.remaining=2_097_152
                    session=self.session(payload['session_id'])
                    if re.search(r'<HG:',raw,re.I):
                        tokens=TOKEN.findall(raw)
                        if re.search(r'<HG:',TOKEN.sub('',raw),re.I) or any(t not in session.entries for t in tokens):return {'allow':False,'reason':'unknown_placeholder'}
                    result=self.walk(request,session)
                    # Any unsupported field, malformed token, work cap, media or
                    # structure that needed withholding denies the entire request.
                    wire=json.dumps(result,ensure_ascii=False)
                    if '[GUARD_WITHHELD_MEDIA:' in wire:return {'allow':False,'reason':'media'}
                    if MARKER in wire:return {'allow':False,'reason':'capacity' if len(session.entries)>=self.limits[1] or session.size>=self.limits[2] else 'unsupported_content'}
                    if self.controls_changed(request,result):return {'allow':False}
                    return {'allow':True,'request':result}
            except (TypeError,ValueError):return {'allow':False,'reason':'unsupported_content'}
            except Exception:return {'allow':False,'reason':'internal'}
        if phase=='tool':
            try:
                result=self.tool_request(payload['tool_name'],payload['args'],session_id=payload['session_id'])
                args=result['args']
                if self.pre_tool(args):return {'allow':False}
                return {'allow':True,'args':args}
            except Exception:return {'allow':False}
        if phase=='output':
            return {'allow':True,'response_text':self.output(**payload)}
        return {'allow':False}

    @staticmethod
    def session_material(value,key='',path=()):
        # Structural credentials, not generic process/session identifiers. No
        # entropy threshold: even a one-character real cookie is sensitive.
        sensitive={'cookie','cookies','set-cookie','set_cookie','localstorage','sessionstorage','storage_state','document.cookie'}
        schema = len(path)>=3 and path[0]=='tools' and isinstance(path[1],int) and path[2] in {'function','input_schema','parameters','parametersJsonSchema','functionDeclarations'}
        if not schema and str(key).lower() in sensitive and value not in (None,'',[],{}):return True
        if isinstance(value,dict):
            return any(Guard.session_material(v,k,path+(k,)) for k,v in value.items())
        if isinstance(value,list):return any(Guard.session_material(v,key,path+(i,)) for i,v in enumerate(value))
        if isinstance(value,str):
            if JWT_MATERIAL.search(value):return True
            if schema:return False  # descriptions and JSON Schema are documentation
            if COOKIE_HEADER.search(value) or SESSION_ASSIGN.fullmatch(value):return True
            try:
                nested=json.loads(value)
            except (ValueError,TypeError):return False
            return isinstance(nested,(dict,list)) and Guard.session_material(nested)
        return False

    @staticmethod
    def controls_changed(before,after):
        # No sensitive control literal is silently sent raw or routed elsewhere.
        # Unknown fields may be masked but must not choose another provider/tool.
        if isinstance(before,dict) and isinstance(after,dict):
            for key,value in before.items():
                protected=after.get(key)
                if key in {'input_schema','parameters','parametersJsonSchema','responseSchema','responseJsonSchema','schema'}:
                    if Guard.schema_controls(value)!=Guard.schema_controls(protected):return True
                if key in STRUCTURE or key in {'tool_choice','provider','routing','order','only','ignore','headers','extra_headers','base_url','user','service_tier','store','metadata','toolUseId','tool_use_id','enum','const','default','required','generationConfig','toolConfig','safetySettings','continuationToken','criteria','stop','stop_sequences','stopSequences'}:
                    if value!=protected:return True
                if Guard.controls_changed(value,protected):return True
        elif isinstance(before,list) and isinstance(after,list):
            return any(Guard.controls_changed(x,y) for x,y in zip(before,after))
        return False

    @staticmethod
    def schema_controls(value):
        """Descriptions may be masked; validation keywords and property names may not."""
        if isinstance(value,dict):
            return {k:({name:Guard.schema_controls(child) for name,child in v.items()}
                       if k in {'properties','patternProperties','$defs','definitions','dependentSchemas'} and isinstance(v,dict)
                       else v if k in {'enum','const','default','examples'} else Guard.schema_controls(v))
                    for k,v in value.items() if k not in {'description','title'}}
        if isinstance(value,list):return [Guard.schema_controls(v) for v in value]
        return value

    def optional_request(self,request,**payload):
        try:
            from agent.privacy_guard import required
            if required():return {'request':request}
        except ImportError:pass
        return self.request(request,**payload)

    def execute(self,request,next_call,session_id='',**kwargs):
        try:
            from agent.privacy_guard import required
            if required():return next_call(request)
        except ImportError:pass
        # Last plugin-level pass before provider execution, including later middleware edits.
        protected=self.request(request,session_id=session_id)['request']
        return next_call(protected)

    def output(self,response_text,session_id='',platform='',**kwargs):
        with self.lock:
            try:
                s=self.session(session_id)
                approved_tokens=set(TOKEN.findall(response_text))
                text=self.text(response_text,s)
                # Native redaction runs BEFORE allowed CLI restoration. The map
                # remains the sole restoration authority; secrets never restore.
                from .output_redact import redact_output
                redacted=redact_output(text)
                if redacted is not None:
                    if redacted.startswith("[OUTPUT_WITHHELD:"):
                        return MARKER
                    text=redacted
                # Only local CLI may restore PII/paths. Credential values stay hidden.
                # API/gateway recipients are not authenticated owner destinations here.
                if platform=='cli':
                    text=TOKEN.sub(lambda m:s.entries[m[0]].value if m[0] in approved_tokens and m[0] in s.entries and s.entries[m[0]].kind in {'PII','IDENTIFIER','PATH'} else m[0],text)
                return text
            except Exception:return MARKER

    def tool_request(self,tool_name,args,session_id='',**kwargs):
        with self.lock:
            try:
                s=self.session(session_id)
                # Restore only a whole known PATH token in the read_file path slot.
                # Never restore into shell, URL, content, messages or unknown tools.
                if not isinstance(tool_name,str) or not tool_name.strip() or not isinstance(args,dict):
                    return {'args':{'_guard_blocked':True}}
                new=dict(args);v=new.get('path')
                if tool_name in {'read_file','write_file','patch','search_files'} and isinstance(v,str):
                    match=TOKEN.match(v)
                    if match and match[0] in s.entries and s.entries[match[0]].kind=='PATH':
                        suffix=v[match.end():]
                        # Exact token or plain relative suffix only; no traversal, whitespace or shell.
                        if not suffix or (re.fullmatch(r'/[A-Za-z0-9_.\-/]+',suffix) and '..' not in suffix.split('/')):
                            new['path']=s.entries[match[0]].value+suffix
                return {'args':new}
            except Exception:return {'args':{'_guard_blocked':True}}

    def pre_tool(self,args,**kwargs):
        if not isinstance(args,dict):return {'action':'block','message':'Tool arguments must be an object.'}
        text=json.dumps(args,default=lambda _:MARKER)
        if '<HG:' in text or '<hg:' in text.lower() or args.get('_guard_blocked'):
            return {'action':'block','message':'Privacy placeholder unresolved or destination not allowed.'}

    def close(self,session_id='',**kwargs):
        with self.lock:self.sessions.pop(session_id,None)

GUARD=Guard()
