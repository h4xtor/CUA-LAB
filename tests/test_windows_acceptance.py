"""Opt-in real Calculator test; scripted planner, no model calls or credentials.

CUA_WINDOWS_TEST=1 python -m pytest tests/test_windows_acceptance.py -s
Requires an unlocked Windows desktop and the installed Cua Driver.
"""
import asyncio
import os
from pathlib import Path

import pytest

from cua_lab.driver import CuaDriverController
from cua_lab.learning import LearningBank
from cua_lab.protocol import Decision, Verification
from cua_lab.runtime import Runtime
from cua_lab.store import Store

pytestmark = pytest.mark.skipif(
    os.name != 'nt' or os.getenv('CUA_WINDOWS_TEST') != '1',
    reason='Opt-in interactive Windows acceptance',
)


class CalculatorPlanner:
    model = 'scripted-local-acceptance-no-inference'
    sequence = [
        (('Clear', 'Ryd'), '0'), (('One', 'En'), '1'),
        (('Nine', 'Ni'), '19'), (('Multiply by', 'Multiplicer med'), '19'),
        (('Two', 'To'), '2'), (('Three', 'Tre'), '23'),
        (('Equals', 'Er lig med'), '437'),
    ]

    def __init__(self):
        self.index = 0

    async def decide(self, context, schemas, image=None):
        window = context['observation'].get('window', {})
        calc = any(name in window.get('window_title', '').lower() for name in ('calculator', 'lommeregner'))
        done = calc and self.index == len(self.sequence)
        if not calc:
            action = {'tool':'launch_app','arguments':{'name':'Calculator'}}
            expected = 'calculator-ready'
        elif not done:
            labels, expected = self.sequence[self.index]
            element = next(e for e in window['elements'] if e.get('label') in labels)
            action = {'tool':'click','arguments':{
                'pid':window['pid'], 'window_id':window['window_id'],
                'element_token':element['element_token'],
            }}
        else:
            action = None
            expected = '437'
        return Decision(
            status='completed' if done else 'continue', observation='Scripted Calculator acceptance',
            user_message='Check real Calculator', action=action, expected_result=expected,
            requires_approval=False, evidence='437' if done else '',
        ), {}

    async def verify(self, context, image=None):
        window = context['observation']['window']
        expected = context['expected_result']
        if expected == 'calculator-ready':
            evidence = window.get('window_title', '')
            satisfied = evidence.lower() in ('calculator', 'lommeregner')
        else:
            expected = '437' if expected.startswith('Calculate') else expected
            evidence = next((e.get('label', '') for e in window.get('elements', [])
                             if e.get('label') in (f'Display is {expected}', f'Skærm er {expected}')), '')
            satisfied = bool(evidence)
            if satisfied and self.index < len(self.sequence):
                self.index += 1
        return Verification(satisfied=satisfied, evidence=evidence or 'Missing Calculator display'), {}


async def test_real_calculator_step_pause_resume_stop_and_result(tmp_path):
    store = Store(tmp_path)
    driver = CuaDriverController(tmp_path)
    runtime = Runtime(store, driver, CalculatorPlanner(), LearningBank(store, tmp_path))

    async def pending():
        async with asyncio.timeout(45):
            while runtime.pending is None:
                if runtime.worker.done():
                    pytest.fail(str(store.events(runtime.sid)[-3:]))
                await asyncio.sleep(.05)

    try:
        async with asyncio.timeout(180):
            await runtime.start('Calculate 19 x 23 and verify 437', mode='step', max_steps=20)
            await pending()
            previous = runtime.pending['id']
            runtime.pause()
            with pytest.raises(ValueError):
                runtime.resolve(previous, 'execute')
            assert runtime.metrics['actions'] == 0
            runtime.resume()
            await pending()
            assert runtime.pending['id'] != previous
            await runtime.stop()
            await runtime.worker
            assert runtime.status == 'stopped' and runtime.metrics['actions'] == 0

            await runtime.start('Calculate 19 x 23 and verify 437', mode='step', max_steps=20)
            while not runtime.worker.done():
                if runtime.pending:
                    runtime.resolve(runtime.pending['id'], 'execute')
                await asyncio.sleep(.05)
            assert runtime.status == 'completed', store.events(runtime.sid)[-3:]
            assert runtime.metrics['actions'] >= 7
            assert runtime.observation['screenshot']
            image = tmp_path/'sessions'/runtime.observation['screenshot']
            assert image.is_file() and image.stat().st_size > 1000
            assert store.learnings()
            print(f'Calculator 437, real UIA clicks and capture PASS; evidence: {image}')
    finally:
        await runtime.stop()
        if runtime.worker:
            await runtime.worker
        await driver.close()
        store.close()
