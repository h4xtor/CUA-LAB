import json
import os
from pathlib import Path

import httpx
import pytest

from cua_lab.configuration import Configuration, ProviderSettings
from cua_lab.local_models import LocalModels
from cua_lab.provider import LocalProvider, OpenRouterProvider, ProviderError


@pytest.mark.parametrize('url', ['https://remote.example:443','http://192.168.1.1:11434','http://localhost:1234/path','http://key@localhost:11434','http://localhost:11434?x=1'])
def test_local_provider_rejects_nonlocal_or_credential_urls(url):
    with pytest.raises(ValueError):ProviderSettings(base_url=url)


@pytest.mark.skipif(os.name!='nt',reason='Windows DPAPI')
def test_saved_key_is_encrypted_and_never_returned(tmp_path):
    config=Configuration(tmp_path)
    config.save(ProviderSettings(model='openrouter/free'),api_key='test-private-credential')
    assert 'test-private-credential' not in config.path.read_text()
    restored=Configuration(tmp_path)
    assert restored.api_key=='test-private-credential'
    assert restored.public()['api_key_configured']
    assert 'test-private-credential' not in json.dumps(restored.public())
    restored.save(restored.settings,clear_key=True)
    assert Configuration(tmp_path).api_key==''


async def test_paid_route_requires_saved_permission(tmp_path):
    provider=OpenRouterProvider(tmp_path,model='paid/model',api_key='fixture',allow_paid=False)
    with pytest.raises(ProviderError,match='credit use'):
        await provider.verify({})
    await provider.close()


@pytest.mark.parametrize('kind', ['ollama','lmstudio'])
async def test_local_structured_response_and_no_cloud_credentials(tmp_path,kind):
    calls=[]
    class Local:
        async def check_model(self, settings): return {'capabilities':['completion','vision']}
    def respond(request):
        calls.append(request)
        assert 'authorization' not in request.headers
        body=json.loads(request.content)
        assert body['stream'] is False
        result=json.dumps({'satisfied':True,'evidence':'437'})
        if kind=='ollama':
            assert body['format']['type']=='object'
            return httpx.Response(200,json={'done':True,'message':{'content':result},'prompt_eval_count':4,'eval_count':3})
        assert body['response_format']['type']=='json_schema'
        return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':result}}],'usage':{'prompt_tokens':4,'completion_tokens':3}})
    client=httpx.AsyncClient(transport=httpx.MockTransport(respond))
    provider=LocalProvider(tmp_path,ProviderSettings(provider=kind,model='test'),Local(),client)
    result,usage=await provider.verify({'expected_result':'437'})
    assert result.satisfied and usage['cost']==0 and usage['input_tokens']==4
    assert calls[0].url.host=='127.0.0.1'
    await provider.close()


async def test_local_cloud_model_refused():
    local=LocalModels()
    async def request(settings,method,path,body=None,timeout=15):
        if path=='/api/tags':return {'models':[{'name':'remote-model'}]}
        return {'remote_host':'https://ollama.com','capabilities':['completion']}
    local.request=request
    with pytest.raises(ValueError,match='Cloud models'):
        await local.check_model(ProviderSettings(provider='ollama',model='remote-model'))


async def test_gguf_import_rejects_wrong_file_and_existing_name(tmp_path):
    local=LocalModels()
    settings=ProviderSettings(provider='ollama')
    source=tmp_path/'fixture.gguf'
    source.write_bytes(b'not a model')
    with pytest.raises(ValueError,match='not a GGUF'):
        await local.import_gguf(settings,str(source),'cua-test')
    source.write_bytes(b'GGUF')
    async def models(settings):return [{'id':'cua-test:latest'}]
    local.models=models
    with pytest.raises(ValueError,match='already exists'):
        await local.import_gguf(settings,str(source),'cua-test')


def test_settings_require_auth_and_cannot_change_during_task(tmp_path):
    from fastapi.testclient import TestClient
    from cua_lab.server import create_app
    app=create_app(tmp_path,token='fixture')
    with TestClient(app) as client:
        assert client.get('/api/models/settings').status_code==401
        headers={'X-Cua-Token':'fixture'}
        assert client.get('/api/models/settings',headers=headers).status_code==200
        body={'settings':{'provider':'openrouter','model':'openrouter/free'}}
        assert client.post('/api/models/settings',headers=headers,json=body).status_code==200
        class Busy:
            def done(self):return False
        app.state.runtime.worker=Busy()
        try:assert client.post('/api/models/settings',headers=headers,json=body).status_code==409
        finally:app.state.runtime.worker=None
    assert Configuration(tmp_path).settings.model=='openrouter/free'
