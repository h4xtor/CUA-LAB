import asyncio
from pathlib import Path
import pytest
from cua_lab.protocol import Decision, Verification
from cua_lab.store import Store
from cua_lab.learning import LearningBank

class Driver:
    schemas={'press_key':{'type':'object','properties':{'key':{'type':'string'},'target':{'type':'object'}},'required':['key','target'],'additionalProperties':False}}
    def __init__(self):self.actions=[];self.value='0';self.observations=0
    async def observe(self,sid,fresh=False,capture=True):
        self.observations+=1
        return {'window':{'pid':1,'window_id':2,'app_name':'Calculator','window_title':'Calculator','elements':[{'label':'Display','value':self.value}]},'windows':[],'screenshot':None,'latency':{}}
    async def execute(self,a):self.actions.append(a);self.value='437';return {'result':{},'execution_ms':1}
    def invalidate(self):pass
    async def close(self):pass

class Provider:
    model='test-only'
    def __init__(self):self.calls=0;self.entered=asyncio.Event();self.hold=False
    async def decide(self,ctx,schemas,image=None):
        self.calls+=1;self.entered.set()
        if self.hold:await asyncio.Event().wait()
        done=ctx['observation']['window']['elements'][0]['value']=='437'
        return Decision(status='completed' if done else 'continue',observation='Calculator',user_message='Read result' if done else 'Press Enter',action=None if done else {'tool':'press_key','arguments':{'key':'enter','target':{'kind':'window','pid':1,'window_id':2}}},expected_result='437',requires_approval=False,evidence='437' if done else ''),{'input_tokens':1,'output_tokens':1,'cost':None}
    async def verify(self,ctx,image=None):return Verification(satisfied=True,evidence='437'),{'input_tokens':1,'output_tokens':1,'cost':None}

async def until(predicate):
    async with asyncio.timeout(2):
        while not predicate():await asyncio.sleep(.005)

def setup(tmp_path):
    from cua_lab.runtime import Runtime
    store=Store(tmp_path);driver=Driver();provider=Provider()
    runtime=Runtime(store,driver,provider,LearningBank(store,Path(tmp_path)))
    return runtime,driver,provider


async def test_desktop_cleanup_plan_is_readonly_and_never_dispatches_input(tmp_path):
    r,d,p=setup(tmp_path);d.preferred_app=None
    await r.start('Vis mig skrivebordet og lav en oprydningsplan')
    await r.worker
    assert d.preferred_app=='Desktop' and r.read_only
    assert d.actions==[] and r.status=='blocked'

async def test_stop_cancels_model_and_all_future_actions(tmp_path):
    r,d,p=setup(tmp_path);p.hold=True
    await r.start('test',mode='auto')
    await p.entered.wait();await r.stop()
    await until(lambda:r.worker.done())
    assert r.status=='stopped' and d.actions==[] and p.calls==1
    p.hold=False
    await r.start('test',mode='auto');await r.worker
    assert r.status=='completed'

async def test_step_mode_waits_and_executes_exactly_once(tmp_path):
    r,d,p=setup(tmp_path)
    await r.start('test',mode='step')
    await until(lambda:r.pending is not None)
    assert d.actions==[]
    r.resolve(r.pending['id'],'execute')
    await r.worker
    assert len(d.actions)==1 and r.status=='completed'

async def test_pause_invalidates_pending_approval(tmp_path):
    r,d,p=setup(tmp_path)
    await r.start('test',mode='step');await until(lambda:r.pending is not None)
    old=r.pending['id'];r.pause()
    with pytest.raises(ValueError):r.resolve(old,'execute')
    assert d.actions==[]
    await r.stop();await until(lambda:r.worker.done())


@pytest.mark.parametrize('choice',['stop','reject'])
async def test_stop_or_reject_before_admission_never_executes(tmp_path,choice):
    r,d,p=setup(tmp_path)
    await r.start('test',mode='step');await until(lambda:r.pending is not None)
    old=r.pending['id']
    if choice=='stop':await r.stop()
    else:r.resolve(old,'reject')
    await r.worker
    assert d.actions==[] and r.status==('stopped' if choice=='stop' else 'blocked')
    with pytest.raises(ValueError):r.resolve(old,'execute')


@pytest.mark.parametrize('supported',[True,False])
async def test_automatic_vision_and_progress_reuse_latest_observation(tmp_path,supported):
    r,d,p=setup(tmp_path)
    async def capability():return supported
    p.supports_vision=capability
    await r.start('test',vision=not supported)
    await r.worker
    assert r.vision is supported and r.status=='completed'
    assert d.observations==4  # initial, admission, after action, final completion
    phases=[e['data']['phase'] for e in r.store.events(r.sid) if e['type']=='progress']
    assert all(name in phases for name in ('preparing','observing','planning','validating','executing','verifying','completed'))
    assert r.snapshot()['progress']['phase']=='completed'


def test_images_only_fill_missing_uia_and_never_bypass_sensitive_state(tmp_path):
    r,_,_=setup(tmp_path);r.vision=True
    obs={'window':{'elements':[{'label':'display'}]},'screenshot':'image.png'}
    assert r.image_for(obs) is None
    obs['window']['elements']=[]
    assert r.image_for(obs)=='image.png'
    obs['screenshot_withheld']=True
    assert r.image_for(obs) is None
    obs['screenshot_withheld']=False;r.vision=False
    assert r.image_for(obs) is None


async def test_automatic_learning_sync_does_not_delay_task_completion(tmp_path):
    from cua_lab.learning import Learning,machine_id
    r,d,p=setup(tmp_path)
    r.store.save_learning(Learning(application='Calculator',problem='calculator_input',strategy='uia_targeting',source_machine=machine_id(),observations=3,successes=3))
    entered=asyncio.Event();release=asyncio.Event()
    async def sync(auto=False):
        assert auto
        entered.set();await release.wait();return []
    r.learning.sync=sync
    r.queue_sync();await entered.wait()
    await r.start('test');await asyncio.wait_for(r.worker,2)
    assert r.status=='completed' and not r.sync_worker.done()
    release.set();await r.sync_worker


async def test_next_plan_remembers_verified_result_without_expired_token(tmp_path):
    r,d,p=setup(tmp_path)
    await r.start('test');await r.worker
    r.recent[-1]['action']['arguments']['element_token']='expired:1'
    context=r.context(r.observation)
    assert context['recent_actions'][-1]['evidence']=='437'
    assert context['recent_actions'][-1]['verified'] is True
    assert 'element_token' not in context['recent_actions'][-1]['action']['arguments']
    assert r.recent[-1]['action']['arguments']['element_token']=='expired:1'


async def test_learning_arriving_during_multiple_uploads_is_drained(tmp_path):
    from cua_lab.learning import Learning,machine_id
    r,_,_=setup(tmp_path)
    r.store.save_learning(Learning(application='Calculator',problem='calculator_input',strategy='uia_targeting',source_machine=machine_id(),observations=3,successes=3))
    uploads=[]
    async def sync(auto=False):
        uploads.append(auto)
        if len(uploads)<3:r.queue_sync()
        await asyncio.sleep(0)
        return []
    r.learning.sync=sync;r.queue_sync();await r.sync_worker
    assert uploads==[True,True,True] and not r.sync_requested
