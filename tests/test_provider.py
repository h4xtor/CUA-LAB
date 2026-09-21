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
    provider=OpenRouterProvider(tmp_path,httpx.AsyncClient(transport=httpx.MockTransport(respond)))
    result,usage=await provider.verify({'expected_result':'437'})
    assert result.satisfied and usage['input_tokens']==7 and usage['cost'] is None
    body=json.loads(captured[0].content)
    assert captured[0].url.path=='/api/v1/responses' and body['store'] is False
    assert 'test-credential-not-real' not in captured[0].content.decode()
    await provider.close()

async def test_auth_error_does_not_echo_provider_body(tmp_path,monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY','test-only')
    client=httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(401,text='private echo')))
    provider=OpenRouterProvider(tmp_path,client)
    with pytest.raises(ProviderError,match='401') as error:await provider.verify({})
    assert 'private echo' not in str(error.value)
    await provider.close()
