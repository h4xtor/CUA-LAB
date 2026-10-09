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


def test_verified_window_location_survives_restart_without_titles_or_tokens(tmp_path):
    store=Store(tmp_path);bank=LearningBank(store,tmp_path)
    obs={'window':{'app_name':'Calculator','window_title':'private title','window_bounds':{'x':10,'y':20,'width':500,'height':700}}}
    bank.detect({'tool':'get_window_state','arguments':{}},obs,obs,True)
    store.close();store=Store(tmp_path);bank=LearningBank(store,tmp_path)
    remembered=bank.relevant(obs)[0]
    assert remembered['last_window_bounds']=={'x':10,'y':20,'width':500,'height':700}
    assert remembered['strategy']=='observed_window'
    assert 'private title' not in json.dumps(remembered)
    store.close()


async def test_new_learning_during_upload_is_not_overwritten_or_marked_synced(tmp_path,monkeypatch):
    store=Store(tmp_path);bank=LearningBank(store,tmp_path)
    record=Learning(application='Calculator',problem='calculator_input',strategy='uia_targeting',source_machine=machine_id(),observations=3,successes=3)
    store.save_learning(record);monkeypatch.setenv('CUA_LAB_GITHUB_TOKEN','fake-test-token')
    uploads=[]
    async def respond(request):
        if request.method=='GET':return httpx.Response(404)
        payload=json.loads(request.content)
        uploads.append(json.loads(base64.b64decode(payload['content'])))
        if len(uploads)==1:
            updated=record.model_copy(update={'observations':4,'successes':4})
            store.save_learning(updated)
        return httpx.Response(201)
    import base64
    real_client=httpx.AsyncClient
    monkeypatch.setattr('cua_lab.learning.httpx.AsyncClient',lambda **kwargs:real_client(transport=httpx.MockTransport(respond),**kwargs))
    await bank.sync(auto=True)
    assert store.learnings()[0]['successes']==4 and not store.learnings()[0]['synced']
    await bank.sync(auto=True)
    assert store.learnings()[0]['synced'] and [r['successes'] for r in uploads]==[3,4]
    store.close()


async def test_sync_uses_authenticated_cli_when_no_explicit_token(tmp_path,monkeypatch):
    import asyncio
    store=Store(tmp_path);bank=LearningBank(store,tmp_path)
    store.save_learning(Learning(application='Calculator',problem='calculator_input',strategy='uia_targeting',source_machine=machine_id(),successes=3,observations=3))
    monkeypatch.delenv('CUA_LAB_GITHUB_TOKEN',raising=False)
    monkeypatch.setattr('cua_lab.learning.shutil.which',lambda name:'gh.exe')
    class Process:
        returncode=0
        async def communicate(self):return b'fixture-private-github-token\n',b''
    async def spawn(*args,**kwargs):
        assert args==('gh.exe','auth','token')
        assert kwargs['stderr']==asyncio.subprocess.DEVNULL
        return Process()
    monkeypatch.setattr('cua_lab.learning.asyncio.create_subprocess_exec',spawn)
    def respond(request):
        assert request.headers['authorization']=='Bearer fixture-private-github-token'
        return httpx.Response(404 if request.method=='GET' else 201)
    real_client=httpx.AsyncClient
    monkeypatch.setattr('cua_lab.learning.httpx.AsyncClient',lambda **kwargs:real_client(transport=httpx.MockTransport(respond),**kwargs))
    assert len(await bank.sync(auto=True))==1
    from cua_lab.privacy import redact
    assert redact('fixture-private-github-token')=='[REDACTED]'
    store.close()
