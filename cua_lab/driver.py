"""Persistent stdio MCP adapter for the installed Cua Driver 0.28.2+."""
import asyncio
import base64
import ctypes
import hashlib
import json
import os
import platform
import shutil
import time
import uuid
from pathlib import Path
from typing import Protocol
from .protocol import public_schemas, validate_action
from .privacy import redact, sensitive_state

class ComputerController(Protocol):
    schemas: dict
    async def observe(self, sid: str, fresh: bool = False) -> dict: ...
    async def execute(self, action: dict) -> dict: ...
    async def close(self): ...
    def invalidate(self): ...

class DriverError(RuntimeError):
    pass

class MCPTransport:
    def __init__(self, command):
        self.command = command
        self.process = None
        self.pending = {}
        self.sequence = 0
        self.reader = None
        self.write_lock = asyncio.Lock()

    async def start(self):
        flags = 0x08000000 if os.name == 'nt' else 0
        env = os.environ.copy()
        # The driver does not need model or GitHub credentials.
        for key in ('OPENROUTER_API_KEY','CUA_LAB_GITHUB_TOKEN'):
            env.pop(key, None)
        self.process = await asyncio.create_subprocess_exec(*self.command, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL, limit=32*1024*1024, creationflags=flags, env=env)
        self.reader = asyncio.create_task(self._read())
        init = await self.request('initialize', {'protocolVersion':'2025-06-18','capabilities':{},'clientInfo':{'name':'CUA LAB','version':'0.1.0'}})
        await self.send({'jsonrpc':'2.0','method':'notifications/initialized'})
        return init

    async def send(self, data):
        async with self.write_lock:
            self.process.stdin.write((json.dumps(data)+'\n').encode())
            await self.process.stdin.drain()

    async def _read(self):
        try:
            while line := await self.process.stdout.readline():
                try:
                    message = json.loads(line)
                except (ValueError, UnicodeDecodeError):
                    continue
                fut = self.pending.get(message.get('id'))
                if fut and not fut.done():
                    if 'error' in message:
                        fut.set_exception(DriverError('Driver protocol refusal'))
                    else:
                        fut.set_result(message.get('result', {}))
        finally:
            for fut in list(self.pending.values()):
                if not fut.done():
                    fut.set_exception(DriverError('Cua Driver disconnected'))

    async def request(self, method, params, timeout=20):
        self.sequence += 1
        rid = self.sequence
        fut = asyncio.get_running_loop().create_future()
        self.pending[rid] = fut
        try:
            await self.send({'jsonrpc':'2.0','id':rid,'method':method,'params':params})
            return await asyncio.wait_for(fut, timeout)
        except (asyncio.CancelledError, TimeoutError):
            # Cancellation prevents any subsequent action. An input already delivered
            # to Windows is not reversible. Terminate only our own MCP process.
            await self.close()
            raise
        finally:
            self.pending.pop(rid, None)

    async def close(self):
        proc = self.process
        if proc and proc.returncode is None:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            await proc.wait()
        if self.reader and self.reader is not asyncio.current_task():
            self.reader.cancel()
            await asyncio.gather(self.reader, return_exceptions=True)

def unpack(result):
    data = result.get('structuredContent')
    if not isinstance(data, dict):
        texts = [c.get('text','') for c in result.get('content',[]) if c.get('type') == 'text']
        data = {}
        for text in texts:
            try:
                decoded = json.loads(text)
                if isinstance(decoded, dict):
                    data.update(decoded)
            except ValueError:
                data.setdefault('summary', text[:6000])
    if result.get('isError'):
        code = data.get('code','tool_failed')
        raise DriverError('Cua Driver refused action: ' + str(code)[:100])
    return data

def active_window():
    if os.name != 'nt':
        return None
    from ctypes import wintypes
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    hwnd = user32.GetForegroundWindow()
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return {'pid':pid.value,'window_id':int(hwnd or 0)}

def machine_profile():
    result = {'hostname':platform.node(),'os':platform.platform(),'monitors':[]}
    if os.name == 'nt':
        from ctypes import wintypes
        class MonitorInfo(ctypes.Structure):
            _fields_ = [('cbSize',wintypes.DWORD),('rcMonitor',wintypes.RECT),('rcWork',wintypes.RECT),('dwFlags',wintypes.DWORD)]
        user32 = ctypes.WinDLL('user32', use_last_error=True)
        callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HMONITOR,wintypes.HDC,ctypes.POINTER(wintypes.RECT),wintypes.LPARAM)
        user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR,ctypes.POINTER(MonitorInfo)]
        def collect(handle, dc, rect, data):
            info = MonitorInfo(); info.cbSize = ctypes.sizeof(info)
            if user32.GetMonitorInfoW(handle, ctypes.byref(info)):
                r=info.rcMonitor
                result['monitors'].append({'x':r.left,'y':r.top,'width':r.right-r.left,'height':r.bottom-r.top,'primary':bool(info.dwFlags & 1)})
            return True
        user32.EnumDisplayMonitors(None,None,callback_type(collect),0)
    return result

class CuaDriverController:
    def __init__(self, root):
        self.root = Path(root)
        self.transport = None
        self.schemas = {}
        self.raw_schemas = {}
        self.target = None
        self.windows = []
        self.version = None
        self.last_observation = {}
        self.lock = asyncio.Lock()
        self.preferred_app = None

    def invalidate(self):
        self.target = None
        self.windows = []
        self.last_observation = {}

    async def connect(self):
        if self.transport and self.transport.process and self.transport.process.returncode is None:
            return
        binary = os.getenv('CUA_DRIVER_PATH') or shutil.which('cua-driver')
        if not binary:
            candidate = Path.home()/'.cua/bin/cua-driver.exe'
            if candidate.is_file():
                binary = str(candidate)
        if platform.system() != 'Windows':
            raise DriverError('Windows interactive desktop required; current environment is '+platform.system())
        if not binary:
            raise DriverError('Cua Driver missing. Install it or set CUA_DRIVER_PATH to its executable.')
        self.transport = MCPTransport([binary,'mcp'])
        try:
            init = await self.transport.start()
            self.version = init.get('serverInfo',{}).get('version','unknown')
            listing = await self.transport.request('tools/list', {})
            self.raw_schemas = {t['name']:t['inputSchema'] for t in listing.get('tools',[])}
            self.schemas = public_schemas(listing.get('tools',[]))
            if not {'list_windows','get_window_state','click'} <= self.schemas.keys():
                raise DriverError('Installed driver lacks required tool contract')
        except BaseException:
            await self.close()
            raise

    async def call(self, name, arguments):
        await self.connect()
        started=time.perf_counter()
        result=await self.transport.request('tools/call', {'name':name,'arguments':arguments})
        data=unpack(result)
        return data, result, round((time.perf_counter()-started)*1000,1)

    async def observe(self, sid, fresh=False):
        async with self.lock:
            if fresh:
                self.invalidate()
            await self.connect()
            started=time.perf_counter()
            if not self.windows:
                data,_,_=await self.call('list_windows',{})
                self.windows=data.get('windows',[])
            active=active_window()
            if self.target is None and self.preferred_app:
                names={'Calculator':('calculator','lommeregner'),'Chrome':('chrome',),'Microsoft Edge':('microsoft edge','msedge')}
                matches=[w for w in self.windows if w.get('pid') and w.get('window_id')
                         and any(term in (str(w.get('title',''))+' '+str(w.get('app_name',''))).lower()
                                 for term in names.get(self.preferred_app,()))]
                if len(matches)==1:
                    self.target={'pid':matches[0]['pid'],'window_id':matches[0]['window_id']}
            if self.target is None and active:
                self.target=next(({'pid':w['pid'],'window_id':w['window_id']} for w in self.windows if w.get('window_id')==active['window_id'] and w.get('pid')),None)
            state={}; image=None; uia_ms=0; shot_ms=0
            if self.target:
                args={**self.target,'include_screenshot':False,'include_accessibility_tree':True,'max_elements':100,'max_depth':8}
                state,_,uia_ms=await self.call('get_window_state',args)
                if not sensitive_state(state):
                    capture={**self.target,'include_accessibility_tree':False,'include_screenshot':True}
                    _,raw,shot_ms=await self.call('get_window_state',capture)
                    # A screenshot-only call must not replace the UIA token map; fresh
                    # tokens are captured after the image for an unambiguous final snapshot.
                    state,_,uia_ms=await self.call('get_window_state',args)
                    image=self._save_image(sid,raw)
                else:
                    state={k:v for k,v in state.items() if k in ('pid','window_id','app_name','window_title')}
                    state['sensitive_interface']='password or credential field detected; use Take Control'
            obs={'active_window':active,'windows':self.windows,'window':state,'screenshot':image,'screenshot_withheld':sensitive_state(state),'latency':{'uia_ms':uia_ms,'screenshot_ms':shot_ms,'observation_ms':round((time.perf_counter()-started)*1000,1)}}
            if not self.windows:
                raise DriverError('No Windows windows detected; check interactive desktop and cua-driver doctor')
            self.last_observation=obs
            return obs

    def _save_image(self,sid,result):
        for item in result.get('content',[]):
            if item.get('type')=='image' and item.get('mimeType') in ('image/png','image/jpeg'):
                payload=base64.b64decode(item['data'], validate=True)
                if len(payload)>24*1024*1024:
                    raise DriverError('Screenshot exceeds size limit')
                folder=self.root/'sessions'/sid/'screenshots';folder.mkdir(parents=True,exist_ok=True)
                name=uuid.uuid4().hex+('.png' if item['mimeType']=='image/png' else '.jpg')
                (folder/name).write_bytes(payload)
                return f'{sid}/screenshots/{name}'
        return None

    async def execute(self, action):
        async with self.lock:
            action=validate_action(action,self.schemas)
            args=action['arguments'];tool=action['tool']
            target=args.get('target',args)
            if target.get('pid') and target.get('window_id'):
                exact={'pid':target['pid'],'window_id':target['window_id']}
                if tool not in ('get_window_state',) and exact!=self.target:
                    raise DriverError('Target not inspected; call get_window_state first')
                self.target=exact
            if args.get('element_token'):
                elements=self.last_observation.get('window',{}).get('elements',[])
                if not any(e.get('element_token')==args['element_token'] for e in elements):
                    raise DriverError('Stale or foreign element token; refresh observation')
            wire_args=dict(args)
            if tool=='launch_app' and args.get('name')=='Calculator' and 'aumid' in self.raw_schemas.get(tool,{}).get('properties',{}):
                wire_args={'aumid':'Microsoft.WindowsCalculator_8wekyb3d8bbwe!App'}
            data,_,ms=await self.call(tool,wire_args)
            if tool in ('list_windows','launch_app','get_desktop_state'):
                self.windows=[]
                if tool=='launch_app':
                    self.target=None
                    # Background launches deliberately preserve the foreground app.
                    # Observe the returned window, rather than the user's foreground.
                    windows=data.get('windows',[])
                    if len(windows)==1 and data.get('pid') and windows[0].get('window_id'):
                        self.target={'pid':data['pid'],'window_id':windows[0]['window_id']}
            return {'result':redact(data),'execution_ms':ms}

    async def close(self):
        if self.transport:
            await self.transport.close()
        self.transport=None
        self.invalidate()

def state_fingerprint(obs):
    state=json.loads(json.dumps(obs.get('window',{})))
    for key in ('snapshot_id','screenshot_file_path'):
        state.pop(key,None)
    if state.get('elements') is not None:
        state.pop('tree_markdown',None)
    for element in state.get('elements',[]) or []:
        element.pop('element_token',None)
    return hashlib.sha256(json.dumps({'window':state,'active':obs.get('active_window'),'windows':obs.get('windows')},sort_keys=True).encode()).hexdigest()
