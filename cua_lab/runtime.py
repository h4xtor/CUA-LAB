import asyncio
import json
import re
import time
import uuid
from . import __version__
from .driver import state_fingerprint
from .privacy import redact
from .protocol import validate_action, READ_TOOLS
from .safety import classify

class Runtime:
    def __init__(self,store,driver,provider,learning):
        self.store=store;self.driver=driver;self.provider=provider;self.learning=learning
        self.worker=None;self.status='idle';self.sid=None;self.step=0;self.pending=None
        self.subscribers=set();self.resume_gate=asyncio.Event();self.resume_gate.set()
        self.epoch=0;self.decision_future=None;self.recent=[];self.observation={}
        self.metrics={};self.started=None;self.auto_sync=self.store.setting('auto_sync',True)
        self.sync_worker=None;self.sync_requested=False
        self.memory_status={'status':'idle' if self.auto_sync else 'disabled','detail':'Automatic GitHub sync ready' if self.auto_sync else 'Automatic sync disabled; learning remains local'}
        self.progress={'phase':'idle','detail':'Ready for a task','since':time.time()}
        self.verification_evidence=''

    def snapshot(self):
        return {'session':self.sid,'status':self.status,'step':self.step,'pending':self.pending,'read_only':getattr(self,'read_only',False),'mode':getattr(self,'mode','auto'),'max_steps':getattr(self,'max_steps',40),'objective':getattr(self,'objective',''),'started':self.started,'metrics':self.metrics,'progress':self.progress,'vision':getattr(self,'vision',False),'auto_sync':self.auto_sync,'memory_sync':self.memory_status,'observation':self.observation,'busy':bool(self.worker and not self.worker.done())}

    def queue_sync(self):
        if not self.auto_sync:return
        eligible=any(not r['synced'] and r['successes']>0 and round((r['successes']+1)/(r['successes']+r['failures']+2),3)>=.8 for r in self.store.learnings())
        if not eligible:return
        self.sync_requested=True
        if not self.sync_worker or self.sync_worker.done():
            self.sync_worker=asyncio.create_task(self._sync_memory(),name='cua-memory-sync')

    async def _sync_memory(self):
        while self.auto_sync and self.sync_requested:
            self.sync_requested=False
            self.memory_status={'status':'syncing','detail':'Sending validated learning to GitHub in the background'}
            self.emit('memory_sync_status',self.memory_status)
            try:
                outcomes=await self.learning.sync(auto=True)
                self.memory_status={'status':'synced','detail':f'{len(outcomes)} learning records sent to GitHub','last_synced':time.time()}
                self.emit('memory_sync',{'synced':outcomes})
            except Exception as exc:
                detail=str(exc) if isinstance(exc,ValueError) and str(exc).startswith(('Set CUA_LAB_GITHUB_TOKEN','GitHub ','Conflicting learning','Forbidden knowledge')) else 'GitHub sync unavailable; learning remains local for retry'
                self.memory_status={'status':'pending','detail':detail}
                self.emit('memory_sync_status',self.memory_status)
                return
            self.emit('memory_sync_status',self.memory_status)

    def phase(self,name,detail):
        self.progress={'phase':name,'detail':detail,'since':time.time(),'step':self.step,'model':self.provider.model}
        self.emit('progress',self.progress.copy())

    def image_for(self,obs):
        window=obs.get('window',{})
        # Use cheap UIA evidence when available; images fill missing UIA coverage.
        useful=any(e.get('role') not in ('Window','Pane','Group','Custom') and (e.get('label') or e.get('value')) for e in window.get('elements',[]))
        needs_image=not useful or window.get('uia_degraded') or window.get('truncated')
        return obs.get('screenshot') if self.vision and needs_image and not obs.get('screenshot_withheld') else None

    def emit(self,kind,data):
        event=self.store.event(self.sid,self.step,kind,data)
        for q in list(self.subscribers):
            if q.full():
                try:q.get_nowait()
                except asyncio.QueueEmpty:pass
            q.put_nowait(event)
        return event

    async def start(self,objective,mode='auto',read_only=False,vision=False,max_steps=40):
        if self.worker and not self.worker.done():raise ValueError('A task is active or stopping; wait for cleanup')
        if not objective.strip() or len(objective)>8000:raise ValueError('Task must contain 1..8000 characters')
        if mode not in ('auto','step'):raise ValueError('Unknown mode')
        if not 1<=max_steps<=100:raise ValueError('max_steps must be 1..100')
        self.sid=uuid.uuid4().hex;self.step=0;self.pending=None;self.epoch+=1
        self.mode=mode;self.vision=False;self.max_steps=max_steps;self.objective=objective
        self.read_only=read_only or bool(re.search(r'(?i)do not (click|modify|change)|read.only|kun (observer|læs)|ikke (klikke|ændre)|\boprydningsplan\b|\bclean(?:up|ing)? plan\b',objective))
        self.status='running';self.resume_gate.set();self.recent=[];self.started=time.time()
        self.observation={};self.progress={'phase':'preparing','detail':'Checking selected model capabilities','since':time.time()}
        self.verification_evidence=''
        self.metrics={'requests':0,'input_tokens':0,'output_tokens':0,'cost':0,'cost_known':True,'failures':0,'actions':0,'retries':0}
        self.driver.invalidate()
        if hasattr(self.driver,'preferred_app'):
            names={'Calculator':r'(?i)\bcalculator\b|\blommeregner\b',
                   'Chrome':r'(?i)\bchrome\b','Microsoft Edge':r'(?i)\bmicrosoft edge\b',
                   'Desktop':r'(?i)\bdesktop\b|\bskrivebord(?:et)?\b'}
            self.driver.preferred_app=next((name for name,pattern in names.items() if re.search(pattern,objective)),None)
        self.store.create(self.sid,objective,{'version':__version__,'model':self.provider.model,'mode':mode,'read_only':self.read_only,'vision':'automatic'})
        self.emit('session_started',self.snapshot())
        self.worker=asyncio.create_task(self._run(),name='cua-task-'+self.sid)
        return self.sid

    def pause(self):
        if not self.worker or self.worker.done():return
        self.epoch+=1;self.resume_gate.clear();self.status='paused'
        if self.decision_future and not self.decision_future.done():self.decision_future.set_result('skip')
        self.pending=None
        self.phase('paused','Paused — resume observes the desktop again')
        self.emit('task_paused',{'detail':'Pending action discarded. Resume will observe again.'})

    def resume(self):
        if self.status!='paused':raise ValueError('Task is not paused')
        self.driver.invalidate();self.epoch+=1;self.status='running';self.resume_gate.set()
        self.phase('observing','Resuming with a fresh observation')
        self.emit('task_resumed',{})

    async def stop(self):
        if self.worker and not self.worker.done():
            self.status='stopped';self.epoch+=1;self.pending=None
            self.worker.cancel()
            self.phase('stopping','Stopping model request and closing driver')
            self.store.finish(self.sid,'stopped')
            self.emit('task_stopped',{'detail':'Cancellation requested; no new calls. Already delivered input cannot be undone.'})
        return self.snapshot()

    def resolve(self,plan_id,choice):
        if choice not in ('execute','skip','reject'):raise ValueError('Unknown decision')
        if not self.pending or self.pending['id']!=plan_id or not self.decision_future or self.decision_future.done():raise ValueError('Stale or missing action approval')
        self.emit('approval',{'plan_id':plan_id,'choice':choice})
        self.decision_future.set_result(choice);self.pending=None

    def usage(self,metric):
        self.metrics['requests']+=1
        for key in ('input_tokens','output_tokens','retries'):
            self.metrics[key]+=metric.get(key,0) or 0
        if metric.get('cost') is None:self.metrics['cost_known']=False
        else:self.metrics['cost']+=metric['cost']
        self.emit('usage',{**metric,'totals':self.metrics.copy()})

    async def observation_now(self,fresh=False,capture=True):
        obs=await self.driver.observe(self.sid,fresh=fresh,capture=capture)
        self.observation=redact(obs)
        self.emit('observation',self.observation)
        return obs

    def context(self,obs):
        recent=json.loads(json.dumps(self.recent[-5:]))
        for record in recent:
            record.get('action',record.get('skipped',{})).get('arguments',{}).pop('element_token',None)
        return {'objective':self.objective,'read_only':self.read_only,'observation':redact(obs),'recent_actions':recent,'knowledge':self.learning.relevant(obs)}

    async def verify(self,obs,expected):
        image=self.image_for(obs)
        self.phase('verifying','Checking observed result: '+expected)
        self.emit('model_request_started',{'purpose':'verification','vision':bool(image)})
        result,usage=await self.provider.verify({'expected_result':expected,'observation':redact(obs)},image=image)
        self.usage(usage)
        # UIA-only verification needs an actual quoted piece of current evidence.
        text=json.dumps(redact(obs.get('window',{})),ensure_ascii=False).casefold()
        text+=' '+json.dumps(obs.get('windows',[]),ensure_ascii=False).casefold()
        grounded=result.evidence.strip().casefold() in text
        satisfied=result.satisfied and (grounded or bool(image))
        self.verification_evidence=result.evidence
        self.emit('verification',{'satisfied':satisfied,'evidence':result.evidence,'grounded_in_uia':grounded})
        return satisfied

    async def _run(self):
        failures=0;duplicates={};fresh=True;before=None;observed_epoch=None
        try:
            async with asyncio.timeout(900):
                self.phase('preparing','Checking selected model capabilities')
                if hasattr(self.provider,'supports_vision'):self.vision=await self.provider.supports_vision()
                self.emit('vision_selected',{'supported':self.vision,'detail':'Screenshots automatic: sent only when UI Automation needs visual evidence' if self.vision else 'Text model: UI Automation evidence only'})
                while self.step<self.max_steps:
                    await self.resume_gate.wait()
                    epoch=self.epoch
                    self.phase('observing','Reading current window and available controls')
                    if before is None or fresh or observed_epoch!=epoch:before=await self.observation_now(fresh=fresh)
                    fresh=False
                    if epoch!=self.epoch:continue
                    self.step+=1;started=time.perf_counter()
                    image=self.image_for(before)
                    self.phase('planning','Waiting for '+self.provider.model+' to choose the next action')
                    self.emit('model_request_started',{'purpose':'plan','vision':bool(image)})
                    try:
                        decision,metric=await self.provider.decide(self.context(before),self.driver.schemas,image=image)
                        self.usage(metric)
                        if epoch!=self.epoch:continue
                        self.emit('model_response',decision.model_dump())
                        if decision.status in ('blocked','failed'):
                            self.status=decision.status;break
                        if decision.status=='completed':
                            self.phase('observing','Reading fresh evidence before accepting completion')
                            current=await self.observation_now()
                            verified=await self.verify(current,self.objective)
                            if epoch!=self.epoch:continue
                            if verified:self.status='completed';break
                            raise ValueError('Completion rejected: objective not grounded in current UI')
                        action=validate_action(decision.action.model_dump(),self.driver.schemas)
                        target_label=next((e.get('label','') for e in before.get('window',{}).get('elements',[]) if e.get('element_token')==action['arguments'].get('element_token')), '') if action['arguments'].get('element_token') else ''
                        reason=classify(action,before,self.read_only)
                        if decision.requires_approval or decision.status=='needs_approval':reason=reason or 'Model requested approval'
                        plan={'id':uuid.uuid4().hex,'action':redact(action),'observation':decision.observation,'expected_result':decision.expected_result,'message':decision.user_message,'approval_reason':reason}
                        self.emit('action_planned',plan)
                        if reason or self.mode=='step':
                            self.pending=plan;self.status='needs_approval' if reason else 'step_wait'
                            self.decision_future=asyncio.get_running_loop().create_future()
                            self.phase('approval',reason or 'Waiting for Execute once')
                            self.emit('approval_required',plan)
                            choice=await self.decision_future
                            self.pending=None
                            if epoch!=self.epoch:continue
                            self.status='running'
                            if choice=='reject':self.status='blocked';break
                            if choice=='skip':
                                self.recent.append({'skipped':action});fresh=True;continue
                        # Desktop may have changed during model latency / user approval.
                        self.phase('validating','Checking desktop and action target before execution')
                        current=await self.observation_now(capture=False)
                        if epoch!=self.epoch:continue
                        if action['tool'] not in READ_TOOLS|{'launch_app'} and state_fingerprint(before,action)!=state_fingerprint(current,action):
                            self.recent.append({'replan':'Desktop changed after planning; approval invalidated'})
                            self.emit('action_invalidated',{'reason':'Desktop changed; replanning'})
                            fresh=True
                            continue
                        if action['arguments'].get('element_token'):
                            old=next((e for e in before.get('window',{}).get('elements',[]) if e.get('element_token')==action['arguments']['element_token']),None)
                            matches=[e for e in current.get('window',{}).get('elements',[]) if old and all(e.get(k)==old.get(k) for k in ('element_index','role','label','value','frame'))]
                            if len(matches)!=1 or not matches[0].get('element_token'):raise ValueError('Element identity changed before execution')
                            action['arguments']['element_token']=matches[0]['element_token']
                        stable=json.loads(json.dumps(action));stable['arguments'].pop('element_token',None)
                        key=state_fingerprint(current,action)+json.dumps(stable,sort_keys=True)
                        duplicates[key]=duplicates.get(key,0)+1
                        if duplicates[key]>=4:raise RuntimeError('Stuck: repeated action without observable state change')
                        # No await occurs between final admission check and execute call.
                        if epoch!=self.epoch:continue
                        self.phase('executing',decision.user_message or action['tool'])
                        self.emit('action_started',{'action':redact(action),'before':current.get('screenshot')})
                        result=await self.driver.execute(action)
                        self.metrics['actions']+=1
                        self.emit('action_result',result)
                        self.phase('observing','Reading the UI after '+action['tool'])
                        after=await self.observation_now()
                        if epoch!=self.epoch:continue
                        verified=await self.verify(after,decision.expected_result)
                        if epoch!=self.epoch:continue
                        self.recent.append({'action':redact(action),'target_label':redact(target_label),'verified':verified,'evidence':redact(self.verification_evidence),'expected':decision.expected_result})
                        learned=self.learning.detect(action,before,after,verified,vision_used=bool(self.image_for(after)))
                        if learned:
                            self.emit('learning_candidate',learned)
                            self.queue_sync()
                        self.emit('step_complete',{'step_ms':round((time.perf_counter()-started)*1000,1),'before':before.get('screenshot'),'after':after.get('screenshot'),'verified':verified})
                        if verified:failures=0;before=after;observed_epoch=epoch
                        else:
                            failures+=1;self.metrics['failures']+=1;fresh=True
                        if failures>=3:raise RuntimeError('Three consecutive unverified actions; task stopped for review')
                    except (ValueError,PermissionError) as exc:
                        failures+=1;self.metrics['failures']+=1
                        # Validation errors may contain model text; never emit exception bodies.
                        message='Action/response rejected by validation, safety or evidence checks'
                        hint='Return exactly one valid decision matching the supplied schema and choose an available tool.'
                        if 'Terminal states cannot contain actions' in str(exc):
                            hint='A blocked, failed or completed decision must set action to null. To act, use continue and supply exactly one action.'
                        elif 'An executable state needs an action' in str(exc):
                            hint='A continue or needs_approval decision must include one available action.'
                        elif 'string_too_long' in str(exc):
                            hint='Keep user_message, observation, evidence and expected_result short and within their schema limits.'
                        elif str(exc).startswith('Click requires'):
                            hint='A click needs a current element_token or both x and y. To inspect the desktop, use get_desktop_state or get_window_state, never click.'
                        self.emit('error',{'message':message,'error_type':type(exc).__name__,'validation_hint':hint})
                        self.recent.append({'failure':message,'validation_hint':hint});fresh=True
                        if failures>=3:self.status='blocked';break
                else:self.status='blocked';self.emit('error',{'message':'Maximum task steps reached'})
        except asyncio.CancelledError:
            self.status='stopped'
        except TimeoutError:
            self.status='failed';self.emit('error',{'message':'Task or driver deadline exceeded'})
        except Exception as exc:
            self.status='failed'
            # Driver/provider errors are deliberately content-free at their source.
            from .driver import DriverError
            from .provider import ProviderError
            detail=str(exc) if isinstance(exc,(DriverError,ProviderError)) else type(exc).__name__
            if str(exc) in ('Stuck: repeated action without observable state change',
                            'Three consecutive unverified actions; task stopped for review'):
                detail=str(exc)
            self.emit('error',{'message':redact(detail)})
        finally:
            self.pending=None
            await self.driver.close()
            self.phase(self.status,{'completed':'Task completed and result verified','blocked':'Task blocked — review the activity log','failed':'Task failed — review the error','stopped':'Stopped; no further actions'}.get(self.status,self.status))
            self.store.finish(self.sid,self.status)
            self.emit('task_'+self.status,{'status':self.status,'metrics':self.metrics})
            self.queue_sync()
