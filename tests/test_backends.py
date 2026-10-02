import json
import os
import sys
import httpx
import pytest
from fastapi.testclient import TestClient
from cua_lab.provider import OpenAICompatibleProvider,LocalGGUFProvider,ProviderError,make_provider,parse_json
from cua_lab.settings import ProviderSettings

FAKE_SERVER='''#!{python}
import json,sys
from http.server import BaseHTTPRequestHandler,HTTPServer
args=sys.argv[1:];port=int(args[args.index('--port')+1]);key=args[args.index('--api-key')+1]
class H(BaseHTTPRequestHandler):
    def log_message(self,*a):pass
    def reply(self,code,body):
        data=json.dumps(body).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
    def do_GET(self):
        self.reply(200,{{'status':'ok'}} if self.path=='/health' else {{'data':[{{'id':'model'}}]}})
    def do_POST(self):
        body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        if self.headers.get('Authorization')!='Bearer '+key:return self.reply(401,{{}})
        assert body['response_format']['type']=='json_schema'
        answer={{'argv':args}} if body.get('echo') else {{'satisfied':True,'evidence':'437'}}
        text='<think>hmm</think>```json\\n'+json.dumps(answer)+'\\n```'
        self.reply(200,{{'choices':[{{'message':{{'content':text}},'finish_reason':'stop'}}],'usage':{{'prompt_tokens':11,'completion_tokens':3}}}})
HTTPServer(('127.0.0.1',port),H).serve_forever()
'''

def test_parse_json_tolerates_reasoning_and_fences():
    assert parse_json('<think>x {"no":1}</think>\n```json\n{"a": 1}\n```')=={'a':1}
    assert parse_json('Sure: {"a": 2} done')=={'a':2}
    with pytest.raises(ProviderError):parse_json('no json here')

async def test_openai_compatible_chat_completions_with_image(tmp_path,monkeypatch):
    monkeypatch.setenv('CUA_LAB_API_KEY','test-key-not-real')
    shots=tmp_path/'sessions'/'s'/'screenshots';shots.mkdir(parents=True);(shots/'a.png').write_bytes(b'png')
    captured=[]
    def respond(request):
        captured.append(request)
        return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps({'satisfied':True,'evidence':'437'})},'finish_reason':'stop'}],'usage':{'prompt_tokens':9,'completion_tokens':2}})
    provider=OpenAICompatibleProvider(tmp_path,'http://localhost:1234/v1/','some-model',httpx.AsyncClient(transport=httpx.MockTransport(respond)))
    result,usage=await provider.verify({'expected_result':'437'},image='s/screenshots/a.png')
    assert result.satisfied and usage['input_tokens']==9 and usage['cost'] is None
    req=captured[0];body=json.loads(req.content)
    assert str(req.url)=='http://localhost:1234/v1/chat/completions' and req.headers['authorization']=='Bearer test-key-not-real'
    assert body['model']=='some-model' and body['response_format']['json_schema']['schema']['title']=='Verification'
    assert body['messages'][1]['content'][1]['image_url']['url'].startswith('data:image/png;base64,')
    await provider.close()

async def test_openai_compatible_rejects_path_escape(tmp_path):
    provider=OpenAICompatibleProvider(tmp_path,'http://x/v1','m',httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(500))))
    with pytest.raises(ProviderError,match='screenshot'):await provider.verify({},image='../secret.png')
    await provider.close()

def fake_server(tmp_path):
    script=tmp_path/'llama-server';script.write_text(FAKE_SERVER.format(python=sys.executable));script.chmod(0o755)
    model=tmp_path/'tiny.gguf';model.write_bytes(b'GGUF')
    return script,model

@pytest.mark.skipif(os.name=='nt',reason='Shebang fixture')
async def test_local_gguf_starts_llama_server_and_answers(tmp_path):
    script,model=fake_server(tmp_path)
    provider=LocalGGUFProvider(tmp_path,str(model),server_path=str(script),context_size=4096,gpu_layers=0,load_timeout=20)
    health=await provider.health()
    assert health['connected'] and not health['model_ready'] and not provider.running
    result,usage=await provider.verify({'expected_result':'437'})
    assert provider.running and result.satisfied and usage['cost']==0.0 and usage['input_tokens']==11
    await provider.close()
    assert not provider.running

@pytest.mark.skipif(os.name=='nt',reason='Shebang fixture')
async def test_local_gguf_passes_model_context_and_mmproj(tmp_path):
    script,model=fake_server(tmp_path)
    proj=tmp_path/'mmproj.gguf';proj.write_bytes(b'GGUF')
    provider=LocalGGUFProvider(tmp_path,str(model),str(proj),str(script),8192,12,load_timeout=20)
    assert provider.supports_vision
    await provider.ensure_started()
    r=await provider.client.post(provider.base_url+'/chat/completions',headers=provider._headers(),json={'echo':True,'response_format':{'type':'json_schema'}})
    argv=parse_json(r.json()['choices'][0]['message']['content'])['argv']
    assert argv[argv.index('-m')+1]==str(model) and argv[argv.index('-c')+1]=='8192' and argv[argv.index('-ngl')+1]=='12'
    assert argv[argv.index('--mmproj')+1]==str(proj) and argv[argv.index('--host')+1]=='127.0.0.1'
    await provider.close()

async def test_local_gguf_reports_missing_pieces(tmp_path):
    provider=LocalGGUFProvider(tmp_path,str(tmp_path/'missing.gguf'),server_path=str(tmp_path/'nope'))
    health=await provider.health()
    assert not health['connected'] and 'not found' in health['detail']
    with pytest.raises(ProviderError,match='not found'):await provider.verify({})
    assert not provider.supports_vision
    await provider.close()

def test_settings_validation_and_factory(tmp_path):
    with pytest.raises(ValueError):ProviderSettings(provider='openai',base_url='file:///etc/passwd')
    assert ProviderSettings(provider='gguf').model_name=='local-gguf'
    assert make_provider(tmp_path,ProviderSettings(provider='openai',base_url='http://localhost:11434/v1/',model='qwen3')).base_url=='http://localhost:11434/v1'
    assert make_provider(tmp_path,ProviderSettings()).name=='openrouter'

def test_provider_switch_persists_and_disables_vision(tmp_path):
    from cua_lab.server import create_app
    headers={'X-Cua-Token':'t'}
    with TestClient(create_app(tmp_path,token='t')) as client:
        assert client.get('/api/provider',headers=headers).json()['active']['provider']=='openrouter'
        model=tmp_path/'m.gguf';model.write_bytes(b'GGUF')
        r=client.post('/api/provider',headers=headers,json={'provider':'gguf','gguf_path':str(model)})
        assert r.status_code==200 and r.json()['active']=={'provider':'gguf','label':'Local GGUF','model':'m','vision':False,'loaded':False}
        assert client.post('/api/tasks',headers=headers,json={'objective':'look','vision':True}).status_code==409
        assert client.post('/api/provider',headers=headers,json={'provider':'nope'}).status_code==422
    with TestClient(create_app(tmp_path,token='t')) as client:
        assert client.get('/api/status',headers=headers).json()['provider']['provider']=='gguf'
