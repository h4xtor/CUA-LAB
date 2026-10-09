import sys
import pytest
from cua_lab.driver import MCPTransport,state_fingerprint


async def test_admission_observation_keeps_uia_tokens_without_capturing_image(tmp_path,monkeypatch):
    from cua_lab.driver import CuaDriverController
    import cua_lab.driver as module
    driver=CuaDriverController(tmp_path);driver.target={'pid':1,'window_id':2};driver.windows=[driver.target]
    calls=[]
    async def connect():pass
    async def call(name,args):
        calls.append(args)
        return {'elements':[{'element_token':'fresh:1'}]}, {}, 1
    driver.connect=connect;driver.call=call
    monkeypatch.setattr(module,'active_window',lambda:None)
    obs=await driver.observe('fixture',capture=False)
    assert len(calls)==1 and calls[0]['include_accessibility_tree']
    assert not calls[0]['include_screenshot'] and obs['screenshot'] is None
    assert obs['window']['elements'][0]['element_token']=='fresh:1'


async def test_token_only_click_binds_inspected_native_window(tmp_path):
    from cua_lab.driver import CuaDriverController
    driver=CuaDriverController(tmp_path);driver.target={'pid':1,'window_id':2}
    driver.schemas={'click':{'type':'object','properties':{'element_token':{'type':'string'}}}}
    driver.last_observation={'window':{'elements':[{'element_token':'fresh:1'}]}}
    async def call(name,args):
        assert args=={'element_token':'fresh:1','pid':1,'window_id':2}
        return {},{},1
    driver.call=call
    await driver.execute({'tool':'click','arguments':{'element_token':'fresh:1'}})


async def test_preview_captures_image_and_tokens_together_after_credential_check(tmp_path,monkeypatch):
    from cua_lab.driver import CuaDriverController
    import cua_lab.driver as module
    driver=CuaDriverController(tmp_path);driver.target={'pid':1,'window_id':2};driver.windows=[driver.target]
    calls=[]
    async def connect():pass
    async def call(name,args):
        calls.append(args)
        return {'elements':[{'element_token':f'snapshot:{len(calls)}'}]}, {}, 1
    driver.connect=connect;driver.call=call
    monkeypatch.setattr(module,'active_window',lambda:None)
    obs=await driver.observe('fixture')
    assert len(calls)==2 and not calls[0]['include_screenshot']
    assert calls[1]['include_accessibility_tree'] and calls[1]['include_screenshot']
    assert obs['window']['elements'][0]['element_token']=='snapshot:2'


async def test_desktop_request_uses_shell_window_instead_of_foreground_app(tmp_path,monkeypatch):
    from cua_lab.driver import CuaDriverController
    import cua_lab.driver as module
    driver=CuaDriverController(tmp_path);driver.preferred_app='Desktop'
    monkeypatch.setattr(module,'desktop_window',lambda:{'pid':10,'window_id':20},raising=False)
    monkeypatch.setattr(module,'active_window',lambda:{'pid':90,'window_id':91})
    async def connect():pass
    async def call(name,args):
        if name=='list_windows':return {'windows':[{'pid':90,'window_id':91,'title':'CUA LAB'}]}, {}, 1
        assert args['pid']==10 and args['window_id']==20
        return {'pid':10,'window_id':20,'window_title':'Program Manager','elements':[]}, {'content':[]}, 1
    driver.connect=connect;driver.call=call
    observation=await driver.observe('fixture')
    assert observation['window']['window_id']==20
    assert driver.target=={'pid':10,'window_id':20}


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


def test_image_capture_metadata_does_not_invalidate_uia_admission():
    state={'window':{'pid':1,'window_id':2,'elements':[{'label':'One','element_token':'fresh:1'}]}}
    preview={'window':{**state['window'],'elements':[{'label':'One','element_token':'fresh:1','screenshot_frame':{'x':1,'y':2,'w':30,'h':40}}],'capture_id':'image:1','screenshot_width':600,'screenshot_height':800,'screenshot_mime_type':'image/png'}}
    assert state_fingerprint(preview)==state_fingerprint(state)


def test_driver_bookkeeping_changes_do_not_invalidate_real_actions():
    before={'window':{'pid':1,'window_id':2,'invalidated_snapshot_ids':['old1'],
                     'walk_elapsed_ms':1,'timeout_ms':200,'elements':[{'label':'One','element_token':'s1:1'}]}}
    after={'window':{**before['window'],'invalidated_snapshot_ids':['old2'],
                    'walk_elapsed_ms':3,'timeout_ms':400,'elements':[{'label':'One','element_token':'s2:1'}]}}
    assert state_fingerprint(before)==state_fingerprint(after)
    after['window']['elements'][0]['label']='Two'
    assert state_fingerprint(before)!=state_fingerprint(after)


def test_exact_window_admission_survives_unrelated_foreground_change():
    before={'window':{'pid':1,'window_id':2,'elements':[{'label':'One'}]},'active_window':{'pid':9},'windows':[]}
    after={**before,'active_window':{'pid':10}}
    action={'tool':'click','arguments':{'pid':1,'window_id':2,'element_token':'s1:1'}}
    assert state_fingerprint(before,action)==state_fingerprint(after,action)
    assert state_fingerprint(before)!=state_fingerprint(after)
    assert state_fingerprint(before,{'arguments':{'target':{'kind':'desktop'}}})!=state_fingerprint(after,{'arguments':{'target':{'kind':'desktop'}}})


def test_token_only_admission_ignores_unrelated_foreground_change():
    before={'window':{'pid':1,'window_id':2,'elements':[{'element_token':'s:1','label':'One'}]},'active_window':{'pid':9},'windows':[]}
    after={**before,'window':{**before['window'],'elements':[{'element_token':'s:2','label':'One'}]},'active_window':{'pid':10}}
    action={'tool':'click','arguments':{'element_token':'s:1'}}
    assert state_fingerprint(before,action)==state_fingerprint(after,action)
    action['arguments']['pid']=3
    assert state_fingerprint(before,action)!=state_fingerprint(after,action)


async def test_missing_requested_app_does_not_capture_unrelated_foreground(tmp_path,monkeypatch):
    from cua_lab.driver import CuaDriverController
    import cua_lab.driver as module
    driver=CuaDriverController(tmp_path)
    driver.preferred_app='Calculator'
    async def connect():pass
    async def call(name,args):
        assert name=='list_windows'
        return {'windows':[{'pid':9,'window_id':90,'title':'Other app'}]}, {}, 1
    driver.connect=connect;driver.call=call
    monkeypatch.setattr(module,'active_window',lambda:{'pid':9,'window_id':90})
    obs=await driver.observe('fixture')
    assert obs['window']=={} and obs['screenshot'] is None
    assert obs['windows'][0]['pid']==9


async def test_uwp_host_and_app_windows_choose_visible_host(tmp_path,monkeypatch):
    from cua_lab.driver import CuaDriverController
    import cua_lab.driver as module
    driver=CuaDriverController(tmp_path);driver.preferred_app='Calculator'
    async def connect():pass
    async def call(name,args):
        if name=='list_windows':
            return {'windows':[{'pid':1,'window_id':2,'title':'Lommeregner','app_name':'ApplicationFrameHost.exe'},
                               {'pid':3,'window_id':4,'title':'Lommeregner','app_name':'CalculatorApp.exe'}]}, {}, 1
        assert args['pid']==1 and args['window_id']==2
        return {'elements':[]}, {'content':[]}, 1
    driver.connect=connect;driver.call=call
    monkeypatch.setattr(module,'active_window',lambda:{'pid':9,'window_id':90})
    await driver.observe('fixture')
    assert driver.target=={'pid':1,'window_id':2}
