"""Model/agent adapters: one JSON contract shared by all native workflows."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from . import secret_store
from .worker_runtime import check_cancelled
from .chatgpt_bridge import extract_json

KINDS={'chatgpt','compatible','anthropic','ollama','claude','codex','opencode'}


def configured():
    data=secret_store.read().get('model_backends',{})
    rows=[]
    for key,cfg in data.items():
        rows.append({k:v for k,v in cfg.items() if k!='api_key'}|{'id':key,'has_key':bool(cfg.get('api_key'))})
    return rows


def configure(identifier,payload):
    if identifier not in KINDS:raise ValueError('Unknown model backend')
    cfg={key:str(payload.get(key,'')).strip() for key in ('base_url','model','api_key')}
    if identifier in {'compatible','anthropic','ollama'}:
        u=urlsplit(cfg['base_url'])
        local=u.hostname in {'localhost','127.0.0.1','::1'}
        if u.username or u.password or u.query or u.fragment or not u.hostname or not (u.scheme=='https' or (local and u.scheme=='http')):
            raise ValueError('Use HTTPS, or HTTP for a local model server')
        if not local:
            from .pfe_discovery import validate_destination
            validate_destination(cfg['base_url'])
        if not cfg['model']:raise ValueError('Choose a model')
    def save(data):
        backends=data.setdefault('model_backends',{})
        if not cfg['api_key']:cfg['api_key']=backends.get(identifier,{}).get('api_key','')
        backends[identifier]=cfg
    secret_store.update(save)


def _http_json(url,body,headers):
    # Do not forward credentials to redirected hosts.
    from urllib.request import build_opener, HTTPRedirectHandler
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs):raise ValueError('Model redirects are not allowed')
    req=Request(url,data=json.dumps(body).encode(),headers={'Content-Type':'application/json',**headers})
    with build_opener(NoRedirect()).open(req,timeout=120) as response:
        raw=response.read(2_000_001)
    if len(raw)>2_000_000:raise ValueError('Model response too large')
    return json.loads(raw)


def _cli(kind,prompt,workspace):
    binary=shutil.which(kind)
    if not binary:raise ValueError(f'{kind} CLI is not installed or not on PATH')
    workspace.mkdir(parents=True,exist_ok=True)
    output=workspace/'agent-response.txt'
    if kind=='codex':args=['exec','--skip-git-repo-check','--sandbox','read-only','--output-last-message',str(output),'-']
    elif kind=='claude':args=['-p','--output-format','json','--tools','']
    else:
        # Isolated task config: these tasks reason over supplied facts only.
        (workspace/'opencode.json').write_text(json.dumps({'$schema':'https://opencode.ai/config.json','permission':'deny'}),encoding='utf-8')
        args=['run','--format','json']
    command=[binary,*args]
    if os.name=='nt' and Path(binary).suffix.lower() in {'.cmd','.bat'}:
        # Resolve standard npm shims to their actual entry points. Never feed
        # candidate paths or prompts through cmd.exe's second parser.
        entries={'codex':'@openai/codex/bin/codex.js','claude':'@anthropic-ai/claude-code/cli.js','opencode':'opencode-ai/bin/opencode'}
        entry=Path(binary).parent/'node_modules'/entries[kind]
        node=shutil.which('node.exe') or shutil.which('node')
        if not entry.is_file() or not node or Path(node).suffix.lower() in {'.cmd','.bat'}:
            raise ValueError('Install the native '+kind+' executable or its standard npm package with Node.js')
        command=[node,str(entry),*args]
    process=subprocess.Popen(command,cwd=workspace,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                             text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    started=time.monotonic();first=True
    try:
        while True:
            check_cancelled()
            try:
                stdout,stderr=process.communicate(input=prompt if first else None,timeout=.5)
                break
            except subprocess.TimeoutExpired:
                first=False
                if time.monotonic()-started>180:raise ValueError('Agent timed out')
        if process.returncode:raise ValueError(f'{kind} failed; check its local sign-in and installation')
        if kind=='codex' and output.exists():return extract_json(output.read_text(encoding='utf-8'))
        try:
            wrapper=json.loads(stdout)
            if isinstance(wrapper,dict) and isinstance(wrapper.get('result'),str):return extract_json(wrapper['result'])
        except ValueError:pass
        if kind=='opencode':
            parts=[]
            for line in stdout.splitlines():
                try:event=json.loads(line)
                except ValueError:continue
                if event.get('type')=='text':parts.append(event.get('part',{}).get('text',event.get('text','')))
            return extract_json('\n'.join(parts))
        return extract_json(stdout)
    finally:
        if process.poll() is None:
            if os.name=='nt':subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
            else:process.kill()


def ask(prompt,backend='chatgpt',*,workspace=None,purpose='capability'):
    if backend not in KINDS:raise ValueError('Unknown model backend')
    check_cancelled()
    if backend=='chatgpt':
        from .profile_store import runtime_profile
        from playwright.sync_api import sync_playwright
        from .chatgpt_bridge import ask_chatgpt_json
        from .browser_control import require_connection,local_endpoint
        profile=runtime_profile();cfg={**profile.get('chatgpt_web_reviewer',{}),'backend':'chatgpt'}
        require_connection(profile)
        with sync_playwright() as p:
            browser=p.chromium.connect_over_cdp(local_endpoint(profile))
            if not browser.contexts:raise ValueError('Open the dedicated Chrome first')
            return ask_chatgpt_json(browser.contexts[0],prompt,cfg,purpose=purpose)
    if backend in {'claude','codex','opencode'}:
        if workspace is None:raise ValueError('Agent task requires its own artifact folder')
        return _cli(backend,prompt,Path(workspace))
    cfg=secret_store.read().get('model_backends',{}).get(backend,{})
    if not cfg.get('base_url') or not cfg.get('model'):raise ValueError('Configure this model backend first')
    base=cfg['base_url'].rstrip('/');key=cfg.get('api_key','')
    if backend=='anthropic':
        obj=_http_json(base+'/messages',{'model':cfg['model'],'max_tokens':6000,'messages':[{'role':'user','content':prompt}]},
                       {'x-api-key':key,'anthropic-version':'2023-06-01'})
        text='\n'.join(part.get('text','') for part in obj.get('content',[]) if part.get('type')=='text')
    elif backend=='ollama':
        obj=_http_json(base+'/api/chat',{'model':cfg['model'],'stream':False,'format':'json','messages':[{'role':'user','content':prompt}]},{})
        text=obj['message']['content']
    else:
        obj=_http_json(base+'/chat/completions',{'model':cfg['model'],'messages':[{'role':'user','content':prompt}],
                        'response_format':{'type':'json_object'}},{'Authorization':'Bearer '+key} if key else {})
        text=obj['choices'][0]['message']['content']
    return extract_json(text)


def status():
    return {'configured':configured(),'agents':{kind:bool(shutil.which(kind)) for kind in ('claude','codex','opencode','career-ops')},
            'browser_available':None,'browser_status':'Use the existing Chrome connection indicator; a model check verifies the session.','kinds':sorted(KINDS)}
