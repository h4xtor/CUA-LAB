import json
import httpx
import pytest
from cua_lab.provider import OpenRouterProvider,ProviderError

async def test_responses_api_parses_usage_without_exposing_key(tmp_path,monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY','test-credential-not-real')
    captured=[]
    def respond(request):
        captured.append(request)
        return httpx.Response(200,json={'model':'qwen/qwen3.7-flash','status':'completed','usage':{'input_tokens':7,'output_tokens':5},'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps({'satisfied':True,'evidence':'437'})}]}]})
    provider=OpenRouterProvider(tmp_path,httpx.AsyncClient(transport=httpx.MockTransport(respond)),model='openrouter/free')
    result,usage=await provider.verify({'expected_result':'437'})
    assert result.satisfied and usage['input_tokens']==7 and usage['cost'] is None
    body=json.loads(captured[0].content)
    assert captured[0].url.path=='/api/v1/responses' and body['store'] is False
    assert 'test-credential-not-real' not in captured[0].content.decode()
    await provider.close()

async def test_auth_error_does_not_echo_provider_body(tmp_path,monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY','test-only')
    client=httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(401,text='private echo')))
    provider=OpenRouterProvider(tmp_path,client,model='openrouter/free')
    with pytest.raises(ProviderError,match='401') as error:await provider.verify({})
    assert 'private echo' not in str(error.value)
    await provider.close()


async def test_plan_grammar_only_admits_current_snapshot_tokens(tmp_path):
    from cua_lab.provider import LocalProvider
    from cua_lab.configuration import ProviderSettings
    schemas={'click':{'type':'object','properties':{'element_token':{'type':'string'}}}}
    class Local:
        async def check_model(self,settings):return {'capabilities':['completion']}
    def respond(request):
        body=json.loads(request.content)
        schema=body['format']
        token_shape=schema['$defs']['Action']['anyOf'][0]['properties']['arguments']['properties']['element_token']
        assert token_shape['enum']==['current:1']
        assert schema['anyOf'][1]['properties']['action']=={'type':'null'}
        return httpx.Response(200,json={'done':True,'message':{'content':json.dumps({
            'status':'continue','observation':'Calculator','user_message':'Click One',
            'action':{'tool':'click','arguments':{'element_token':'current:1'}},
            'expected_result':'Display 1','requires_approval':False,'evidence':'',
        })}})
    provider=LocalProvider(tmp_path,ProviderSettings(provider='ollama',model='test'),Local(),
                           httpx.AsyncClient(transport=httpx.MockTransport(respond)))
    try:
        decision,_=await provider.decide({'observation':{'window':{'elements':[{'element_token':'current:1'}]}}},schemas)
        assert decision.action.arguments['element_token']=='current:1'
        assert 'enum' not in schemas['click']['properties']['element_token']
    finally:await provider.close()


async def test_incomplete_local_response_is_never_accepted_as_an_action(tmp_path):
    from cua_lab.provider import LocalProvider
    from cua_lab.configuration import ProviderSettings
    class Local:
        async def check_model(self,settings):return {'capabilities':['completion']}
    response={'done':True,'done_reason':'length','message':{'content':'{"satisfied":true,"evidence":"437"}'}}
    provider=LocalProvider(tmp_path,ProviderSettings(provider='ollama',model='fixture'),Local(),
        httpx.AsyncClient(transport=httpx.MockTransport(lambda request:httpx.Response(200,json=response))))
    try:
        with pytest.raises(ProviderError,match='response limit.*No action.*Models'):
            await provider.verify({'expected_result':'437'})
        assert provider.requests==0
    finally:await provider.close()


async def test_local_capabilities_cached_across_plan_and_verification(tmp_path):
    from cua_lab.provider import LocalProvider
    from cua_lab.configuration import ProviderSettings
    class Local:
        checks=0
        async def check_model(self,settings):
            self.checks+=1
            return {'capabilities':['completion','vision']}
    local=Local()
    provider=LocalProvider(tmp_path,ProviderSettings(provider='ollama',model='fixture'),local,
        httpx.AsyncClient(transport=httpx.MockTransport(lambda request:httpx.Response(200,json={
            'done':True,'message':{'content':'{"satisfied":true,"evidence":"437"}'}}))))
    try:
        assert await provider.supports_vision()
        await provider.verify({});await provider.verify({})
        assert local.checks==1
    finally:await provider.close()


def test_compact_plan_keeps_controls_without_duplicate_metadata():
    from cua_lab.provider import LocalProvider
    context={'observation':{'window':{'elements':[
        {'element_token':'s:1','label':'One','value':'One','role':'Button','actions':['invoke'],'enabled':True,'frame':{'x':10},'screenshot_frame':{'x':10}},
        {'label':'Visual target','frame':{'x':20}},
    ]}},'available_tools':{'click':{'type':'object','properties':{'element_token':{'type':'string','enum':['s:1']}}}}}
    compact=LocalProvider._compact_context(context)
    element=compact['observation']['window']['elements'][0]
    assert element=={'element_token':'s:1','label':'One','role':'Button','actions':['invoke'],'enabled':True}
    assert compact['observation']['window']['elements'][1]['frame']=={'x':20}
    assert 'enum' not in compact['available_tools']['click']['properties']['element_token']
    assert context['observation']['window']['elements'][0]['value']=='One'


@pytest.mark.parametrize('modalities',[['text'],['text','image']])
async def test_openrouter_vision_follows_selected_catalog_model(tmp_path,modalities):
    provider=OpenRouterProvider(tmp_path,httpx.AsyncClient(transport=httpx.MockTransport(
        lambda request:httpx.Response(200,json={'data':[{'id':'fixture','architecture':{'input_modalities':modalities}}]}))),model='fixture')
    try:assert await provider.supports_vision() is ('image' in modalities)
    finally:await provider.close()


@pytest.mark.parametrize('error,expected',[('CUDA error: out of memory private echo','available GPU memory'),('CUDA devices busy or unavailable private echo','GPU is busy')])
async def test_local_gpu_error_is_actionable_without_echoing_engine_output(tmp_path,error,expected):
    from cua_lab.provider import LocalProvider
    from cua_lab.configuration import ProviderSettings
    class Local:
        async def check_model(self,settings):return {'capabilities':['completion']}
    provider=LocalProvider(tmp_path,ProviderSettings(provider='ollama',model='fixture'),Local(),
        httpx.AsyncClient(transport=httpx.MockTransport(lambda request:httpx.Response(500,json={'error':error}))))
    try:
        with pytest.raises(ProviderError,match=expected) as exc:await provider.verify({})
        assert 'private echo' not in str(exc.value) and provider.requests==0
    finally:await provider.close()
