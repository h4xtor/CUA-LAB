import sys
import pytest
from cua_lab.driver import MCPTransport,state_fingerprint

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
