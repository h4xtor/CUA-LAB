import sys
import pytest
from cua_lab.driver import MCPTransport,state_fingerprint


async def test_requested_calculator_is_observed_even_when_another_app_is_foreground(tmp_path, monkeypatch):
    from cua_lab.driver import CuaDriverController
    import cua_lab.driver as module
    controller=CuaDriverController(tmp_path)
    controller.preferred_app='Calculator'
    async def connect():pass
    async def call(name,args):
        if name=='list_windows':return {'windows':[{'pid':9,'window_id':90,'title':'Other app'},{'pid':1,'window_id':2,'title':'Lommeregner'}]}, {}, 1
        return {'pid':1,'window_id':2,'app_name':'Calculator','elements':[]}, {'content':[]}, 1
    controller.connect=connect
    controller.call=call
    monkeypatch.setattr(module,'active_window',lambda:{'pid':9,'window_id':90})
    observation=await controller.observe('fixture')
    assert controller.target=={'pid':1,'window_id':2}
    assert observation['window']['app_name']=='Calculator'


@pytest.mark.parametrize('windows,expected', [([{'window_id':22}], {'pid':11,'window_id':22}), ([], None), ([{'window_id':22},{'window_id':23}], None)])
async def test_launch_tracks_exact_returned_window(tmp_path, windows, expected):
    from cua_lab.driver import CuaDriverController
    driver = CuaDriverController(tmp_path)
    driver.schemas = {'launch_app': {'type':'object','properties':{'name':{'enum':['Calculator']}}}}
    driver.target = {'pid':99,'window_id':100}
    async def call(name, arguments):
        return {'pid':11,'windows':windows}, {}, 1
    driver.call = call
    await driver.execute({'tool':'launch_app','arguments':{'name':'Calculator'}})
    assert driver.target == expected

async def test_persistent_mcp_transport_and_owned_process_cleanup(tmp_path):
    script=tmp_path/'fake_driver.py'
    script.write_text('''import sys,json
for line in sys.stdin:
 r=json.loads(line)
 if 'id' in r:
  print(json.dumps({'jsonrpc':'2.0','id':r['id'],'result':{'serverInfo':{'version':'test'},'method':r['method']}}),flush=True)
''')
    transport=MCPTransport([sys.executable,str(script)])
    init=await transport.start();pid=transport.process.pid
    assert init['serverInfo']['version']=='test'
    result=await transport.request('tools/list',{})
    assert result['method']=='tools/list' and transport.process.pid==pid
    await transport.close()
    assert transport.process.returncode is not None

def test_snapshot_tokens_do_not_look_like_desktop_changes():
    before={'window':{'snapshot_id':'s1','elements':[{'element_token':'s1:1','label':'equals'}],'tree_markdown':'s1'}}
    after={'window':{'snapshot_id':'s2','elements':[{'element_token':'s2:1','label':'equals'}],'tree_markdown':'s2'}}
    assert state_fingerprint(before)==state_fingerprint(after)
