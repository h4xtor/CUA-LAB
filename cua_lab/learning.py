"""Only closed-vocabulary, aggregate learnings can leave the local machine."""
import asyncio
import base64
import hashlib
import json
import os
import platform
import time
from typing import Literal
import httpx
from pydantic import BaseModel, ConfigDict, Field, computed_field

REPOSITORY='h4xtor/CUA-LAB'
PREFIX='cua_knowledge/'
APPLICATIONS=('Calculator','Chrome','Microsoft Edge','Discord','Unknown')

class Learning(BaseModel):
    model_config=ConfigDict(extra='forbid', strict=True)
    application: Literal['Calculator','Chrome','Microsoft Edge','Discord','Unknown']
    problem: Literal['degraded_uia','calculator_input','address_bar_focus']
    strategy: Literal['visual_fallback','uia_targeting','keyboard_shortcut']
    scope: Literal['global','machine']='machine'
    source_machine: str=Field(pattern=r'^[a-f0-9]{16}$')
    observations: int=Field(default=1,ge=1,le=1000000)
    successes: int=Field(default=0,ge=0,le=1000000)
    failures: int=Field(default=0,ge=0,le=1000000)
    last_validated: int=Field(default=0,ge=0)

    @property
    def id(self):
        key=f'{self.scope}|{self.application}|{self.problem}|{self.strategy}|{self.source_machine}'
        return hashlib.sha256(key.encode()).hexdigest()[:24]

    @property
    def confidence(self):
        return round((self.successes+1)/(self.successes+self.failures+2),3)

def machine_id():
    return hashlib.sha256(platform.node().encode()).hexdigest()[:16]

def knowledge_path(record):
    # No path, filename, code, URL or arbitrary text is accepted from the model.
    record=Learning.model_validate(record.model_dump())
    branch='global/learned' if record.scope=='global' else 'machines/'+record.source_machine
    return PREFIX+branch+'/'+record.id+'.json'

def application_name(obs):
    window=obs.get('window',{})
    value=(str(window.get('app_name',''))+' '+str(window.get('window_title',''))).lower()
    for key,name in [('calculator','Calculator'),('lommeregner','Calculator'),('chrome','Chrome'),('edge','Microsoft Edge'),('discord','Discord')]:
        if key in value:return name
    return 'Unknown'

class LearningBank:
    def __init__(self,store,resource_root):
        self.store=store;self.root=resource_root;self.lock=asyncio.Lock()
        self.shared=[]
        folder=resource_root/'cua_knowledge'
        if folder.exists():
            for p in folder.rglob('*.json'):
                try:
                    record=Learning.model_validate_json(p.read_text())
                    self.shared.append(record)
                except (ValueError,OSError):continue
        for p in (store.root/'cache/knowledge').glob('*.json'):
            try:self.shared.append(Learning.model_validate_json(p.read_text()))
            except (ValueError,OSError):continue

    def detect(self, action, before, after, verified, vision_used=False):
        app=application_name(after)
        tool=action['tool'];args=action['arguments'];problem=None;strategy=None
        if before.get('window',{}).get('degraded') and vision_used:
            problem='degraded_uia';strategy='visual_fallback'
        elif app=='Calculator' and tool=='click' and args.get('element_token'):
            problem='calculator_input';strategy='uia_targeting'
        elif app in ('Chrome','Microsoft Edge') and tool=='hotkey' and [k.lower() for k in args.get('keys',[])] in (['ctrl','l'],['control','l']):
            problem='address_bar_focus';strategy='keyboard_shortcut'
        if not problem:return None
        record=Learning(application=app,problem=problem,strategy=strategy,source_machine=machine_id())
        existing=next((r for r in self.store.learnings() if Learning.model_validate({k:v for k,v in r.items() if k!='synced'}).id==record.id),None)
        if existing:
            record=Learning.model_validate({k:v for k,v in existing.items() if k!='synced'})
            record.observations+=1
        if verified:record.successes+=1
        else:record.failures+=1
        record.last_validated=int(time.time())
        self.store.save_learning(record)
        return {**record.model_dump(),'id':record.id,'confidence':record.confidence}

    def relevant(self, obs):
        app=application_name(obs)
        local=[Learning.model_validate({k:v for k,v in r.items() if k!='synced'}) for r in self.store.learnings()]
        records=[r for r in local+self.shared if r.application==app and (r.scope=='global' or r.source_machine==machine_id()) and r.successes>0]
        records.sort(key=lambda r:(r.source_machine==machine_id(),r.confidence,r.last_validated),reverse=True)
        return [{**r.model_dump(),'confidence':r.confidence} for r in records[:4]]

    async def refresh(self):
        # Read-only, fixed repository. Network failure never discards local knowledge.
        async with httpx.AsyncClient(timeout=15,follow_redirects=False) as client:
            r=await client.get(f'https://api.github.com/repos/{REPOSITORY}/git/trees/main?recursive=1')
            r.raise_for_status()
            count=0
            for entry in r.json().get('tree',[]):
                path=entry.get('path','')
                if not path.startswith(PREFIX) or not path.endswith('.json') or entry.get('size',100000)>8192:continue
                if count>=100:break
                raw=await client.get(f'https://api.github.com/repos/{REPOSITORY}/git/blobs/{entry["sha"]}')
                raw.raise_for_status()
                try:record=Learning.model_validate_json(base64.b64decode(raw.json()['content']))
                except (ValueError,KeyError):continue
                if path!=knowledge_path(record):continue
                folder=self.store.root/'cache/knowledge';folder.mkdir(parents=True,exist_ok=True)
                (folder/(record.id+'.json')).write_text(record.model_dump_json(),encoding='utf-8')
                self.shared=[x for x in self.shared if x.id!=record.id]+[record];count+=1
            return count

    async def sync(self,auto=False):
        async with self.lock:
            token=os.getenv('CUA_LAB_GITHUB_TOKEN','').strip()
            if not token:raise ValueError('Set CUA_LAB_GITHUB_TOKEN with Contents write access to h4xtor/CUA-LAB. Candidates remain local.')
            outcomes=[]
            async with httpx.AsyncClient(timeout=20,follow_redirects=False,headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json'}) as client:
                for raw in self.store.learnings():
                    if raw['synced']:continue
                    record=Learning.model_validate({k:v for k,v in raw.items() if k!='synced'})
                    if record.successes<1 or record.confidence<(.8 if auto else .6):continue
                    path=knowledge_path(record)
                    # Payload consists entirely of closed enums, hashes and aggregate counts.
                    if not path.startswith(PREFIX) or '..' in path or not path.endswith('.json'):raise ValueError('Forbidden knowledge destination')
                    url=f'https://api.github.com/repos/{REPOSITORY}/contents/{path}'
                    current=await client.get(url,params={'ref':'main'})
                    sha=None
                    if current.status_code==200:
                        info=current.json();sha=info['sha']
                        old=Learning.model_validate_json(base64.b64decode(info['content']))
                        if old.id!=record.id:raise ValueError('Conflicting learning identity; kept pending')
                        # Same machine counter is monotonic; never sum a previously synced total.
                        record.observations=max(record.observations,old.observations)
                        record.successes=max(record.successes,old.successes)
                        record.failures=max(record.failures,old.failures)
                        record.last_validated=max(record.last_validated,old.last_validated)
                    elif current.status_code!=404:
                        raise ValueError(f'GitHub read HTTP {current.status_code}; candidates kept pending')
                    payload={'message':'memory: validate '+record.problem,'branch':'main','content':base64.b64encode((record.model_dump_json(indent=2)+'\n').encode()).decode()}
                    if sha:payload['sha']=sha
                    written=await client.put(url,json=payload)
                    if written.status_code not in (200,201):raise ValueError(f'GitHub write HTTP {written.status_code}; candidate kept pending; no force overwrite')
                    self.store.save_learning(record,synced=True)
                    outcomes.append({'id':record.id,'path':path})
            return outcomes
