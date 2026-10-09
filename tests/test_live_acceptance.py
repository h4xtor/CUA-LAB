"""Opt-in autonomous acceptance; uses an explicitly selected installed local Qwen.

CUA_LIVE_TEST=1 python -m pytest tests/test_live_acceptance.py -s
CUA_LIVE_MODEL=qwen3-vl:8b selects an installed alternative.
Screenshots follow selected model capabilities and available UIA evidence.
The default remains qwen2.5vl:7b.
Evidence stays in pytest's private temporary directory, never in Git.
"""
import asyncio
import json
import os
import time

import pytest

from cua_lab.configuration import ProviderSettings
from cua_lab.driver import CuaDriverController
from cua_lab.learning import LearningBank
from cua_lab.model_service import ModelService
from cua_lab.runtime import Runtime
from cua_lab.safety import classify
from cua_lab.store import Store

pytestmark = pytest.mark.skipif(
    os.name != 'nt' or os.getenv('CUA_LIVE_TEST') != '1',
    reason='Opt-in real desktop and installed qwen2.5vl:7b inference',
)


async def test_autonomous_local_qwen_calculator(tmp_path):
    service = ModelService(tmp_path)
    store = Store(tmp_path)
    driver = CuaDriverController(tmp_path)
    runtime = Runtime(store, driver, service, LearningBank(store, tmp_path))
    runtime.auto_sync=False  # Model acceptance must not publish test data.
    settings = ProviderSettings(provider='ollama', model=os.getenv('CUA_LIVE_MODEL','qwen2.5vl:7b'))
    started = time.perf_counter()
    emit = runtime.emit

    def progress(kind, data):
        if kind in ('model_request_started', 'model_response', 'verification', 'error', 'action_started'):
            detail = data.get('status') or data.get('purpose') or data.get('message') or data.get('evidence') or data.get('action', {}).get('tool')
            print(f'{time.perf_counter()-started:.1f}s {kind}: {detail}', flush=True)
        return emit(kind, data)

    runtime.emit = progress
    try:
        await service.local.start(settings)
        await service.save(settings)
        async def local_error(response):
            await response.aread()
            if not response.is_success:
                (tmp_path/'local-http-error.txt').write_text(response.text,encoding='utf-8')
            elif response.request.url.path == '/api/chat':
                data=response.json()
                with (tmp_path/'local-generation.jsonl').open('a',encoding='utf-8') as output:
                    output.write(json.dumps({
                        'done_reason':data.get('done_reason'), 'output_tokens':data.get('eval_count'),
                        'thinking_chars':len(data.get('message',{}).get('thinking','')),
                        'content':data.get('message',{}).get('content',''),
                    },ensure_ascii=False)+'\n')
        service.current.client.event_hooks['response']=[local_error]
        request=service.current._request
        async def record_response(*args, **kwargs):
            result, metric=await request(*args, **kwargs)
            with (tmp_path/'model-responses.jsonl').open('a',encoding='utf-8') as output:
                output.write(json.dumps({'response':result,'usage':metric},ensure_ascii=False)+'\n')
            return result, metric
        service.current._request=record_response
        # Start with a known empty display; this is setup, never the solver.
        driver.preferred_app='Calculator'
        before=await driver.observe('health',fresh=True)
        window=before.get('window',{})
        clear=next((e for e in window.get('elements',[]) if e.get('label') in ('Clear','Ryd')),None)
        if clear:
            await driver.execute({'tool':'click','arguments':{
                'pid':window['pid'],'window_id':window['window_id'],'element_token':clear['element_token'],
            }})
        await runtime.start(
            'Open Calculator and calculate 19 x 23. Verify the final result '
            'from the Calculator display. Use the observed UIA buttons.',
            mode='auto', max_steps=20, vision=os.getenv('CUA_LIVE_VISION')=='1',
        )
        async with asyncio.timeout(600):
            while not runtime.worker.done():
                if runtime.pending:
                    # The user approved this local Calculator exercise only.
                    # Do not turn the harness into a general approval bypass.
                    reason=classify(runtime.pending['action'],runtime.observation)
                    runtime.resolve(runtime.pending['id'],'reject' if reason else 'execute')
                await asyncio.sleep(.05)
        events = store.events(runtime.sid)
        (tmp_path/'live-evidence.json').write_text(json.dumps({
            'status':runtime.status, 'metrics':runtime.metrics, 'events':events,
            'elapsed_s':round(time.perf_counter()-started, 2),
        }, ensure_ascii=False), encoding='utf-8')
        print(f'Private live evidence: {tmp_path}', flush=True)
        assert runtime.status == 'completed', [e['data'] for e in events if e['type']=='error']
        assert runtime.metrics['actions'] > 0
        window = runtime.observation.get('window', {})
        assert any(e.get('label') in ('Display is 437', 'Skærm er 437')
                   for e in window.get('elements', []))
        assert any(e['type']=='model_response' for e in events)
        assert any(e['type']=='verification' and e['data']['satisfied'] for e in events)
    finally:
        await runtime.stop()
        if runtime.worker:
            await asyncio.gather(runtime.worker, return_exceptions=True)
        await driver.close()
        await service.local.request(settings,'POST','/api/generate',{'model':settings.model,'stream':False,'keep_alive':0},timeout=20)
        await service.close()
        store.close()


async def test_stop_during_real_local_model_wait(tmp_path):
    service=ModelService(tmp_path);store=Store(tmp_path)
    driver=CuaDriverController(tmp_path)
    runtime=Runtime(store,driver,service,LearningBank(store,tmp_path))
    waiting=asyncio.Event()
    async def trace(name,info):
        if name=='http11.receive_response_headers.started':waiting.set()
    async def watch(request):
        if request.url.path=='/api/chat':request.extensions['trace']=trace
    try:
        settings=ProviderSettings(provider='ollama',model=os.getenv('CUA_LIVE_MODEL','qwen2.5vl:7b'))
        await service.local.start(settings);await service.save(settings)
        service.current.client.event_hooks['request']=[watch]
        await runtime.start('Read the Calculator display. Do not click or change anything.',read_only=True)
        await asyncio.wait_for(waiting.wait(),90)
        started=time.perf_counter()
        await runtime.stop();await asyncio.wait_for(runtime.worker,10)
        elapsed=time.perf_counter()-started
        await asyncio.sleep(.2)
        events=store.events(runtime.sid)
        assert runtime.status=='stopped' and runtime.metrics['actions']==0
        assert not any(e['type']=='action_started' for e in events)
        (tmp_path/'stop-evidence.json').write_text(json.dumps({
            'status':runtime.status,'stop_cleanup_s':round(elapsed,3),'events':events,
        },ensure_ascii=False),encoding='utf-8')
        print(f'Real local model wait STOP PASS ({elapsed:.3f}s); private evidence: {tmp_path}',flush=True)
    finally:
        await runtime.stop()
        if runtime.worker:await asyncio.gather(runtime.worker,return_exceptions=True)
        await driver.close()
        await service.local.request(settings,'POST','/api/generate',{'model':settings.model,'stream':False,'keep_alive':0},timeout=20)
        await service.close();store.close()
