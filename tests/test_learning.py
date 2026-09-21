from pathlib import Path
import json
import httpx
import pytest
from cua_lab.store import Store
from cua_lab.learning import LearningBank,Learning,knowledge_path,machine_id

def test_automatic_learning_survives_restart(tmp_path):
    store=Store(tmp_path);bank=LearningBank(store,Path(tmp_path))
    obs={'window':{'app_name':'Calculator','elements':[]}}
    record=bank.detect({'tool':'click','arguments':{'element_token':'s1:1'}},obs,obs,True)
    assert record and record['successes']==1
    store.close();store=Store(tmp_path)
    assert len(store.learnings())==1 and not store.learnings()[0]['synced']
    store.close()

def test_machine_knowledge_does_not_leak_to_other_machine(tmp_path):
    store=Store(tmp_path);bank=LearningBank(store,Path(tmp_path))
    store.save_learning(Learning(application='Calculator',problem='calculator_input',strategy='uia_targeting',source_machine='b'*16,successes=1))
    assert bank.relevant({'window':{'app_name':'Calculator'}})==[]
    store.close()

async def test_sync_writes_only_closed_knowledge_record(tmp_path,monkeypatch):
    store=Store(tmp_path);bank=LearningBank(store,Path(tmp_path));calls=[]
    record=Learning(application='Calculator',problem='calculator_input',strategy='uia_targeting',source_machine=machine_id(),successes=1)
    store.save_learning(record);monkeypatch.setenv('CUA_LAB_GITHUB_TOKEN','fake-test-token')
    def respond(request):
        calls.append(request)
        if request.method=='GET':return httpx.Response(404)
        body=json.loads(request.content)
        assert body['branch']=='main'
        assert request.url.path=='/repos/h4xtor/CUA-LAB/contents/'+knowledge_path(record)
        return httpx.Response(201,json={})
    real_client=httpx.AsyncClient
    monkeypatch.setattr('cua_lab.learning.httpx.AsyncClient',lambda **kwargs:real_client(transport=httpx.MockTransport(respond),**kwargs))
    assert len(await bank.sync())==1
    assert len(calls)==2 and store.learnings()[0]['synced']
    store.close()

async def test_sync_conflict_keeps_candidate(tmp_path,monkeypatch):
    store=Store(tmp_path);bank=LearningBank(store,Path(tmp_path))
    record=Learning(application='Calculator',problem='calculator_input',strategy='uia_targeting',source_machine=machine_id(),successes=1)
    store.save_learning(record);monkeypatch.setenv('CUA_LAB_GITHUB_TOKEN','fake-test-token')
    real_client=httpx.AsyncClient
    monkeypatch.setattr('cua_lab.learning.httpx.AsyncClient',lambda **kwargs:real_client(transport=httpx.MockTransport(lambda r:httpx.Response(404 if r.method=='GET' else 409)),**kwargs))
    with pytest.raises(ValueError,match='409'):await bank.sync()
    assert not store.learnings()[0]['synced']
    store.close()
