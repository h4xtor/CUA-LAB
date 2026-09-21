import asyncio
from pathlib import Path
import pytest
from cua_lab.protocol import Decision, Verification
from cua_lab.store import Store
from cua_lab.learning import LearningBank

class Driver:
    schemas={'press_key':{'type':'object','properties':{'key':{'type':'string'},'target':{'type':'object'}},'required':['key','target'],'additionalProperties':False}}
    def __init__(self):self.actions=[];self.value='0';self.observations=0
    async def observe(self,sid,fresh=False):
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
