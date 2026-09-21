import asyncio
import hmac
import json
import platform
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from . import __version__
from .driver import CuaDriverController,machine_profile,DriverError
from .provider import OpenRouterProvider
from .runtime import Runtime
from .store import Store
from .learning import LearningBank,Learning

class TaskInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    objective:str=Field(min_length=1,max_length=8000)
    mode:Literal['auto','step']='auto'
    read_only:bool=False
    vision:bool=False
    max_steps:int=Field(default=40,ge=1,le=100)

class ApprovalInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    plan_id:str
    choice:Literal['execute','skip','reject']

def create_app(root=None,token=None,driver=None,provider=None):
    resource_root=Path(__file__).resolve().parent.parent
    store=Store(root);driver=driver or CuaDriverController(store.root)
    provider=provider or OpenRouterProvider(store.root)
    bank=LearningBank(store,resource_root);runtime=Runtime(store,driver,provider,bank)
    token=token or secrets.token_urlsafe(32)
    profile=machine_profile()
    (store.root/'machine/profile.json').write_text(json.dumps(profile,indent=2),encoding='utf-8')

    @asynccontextmanager
    async def lifespan(app):
        yield
        if runtime.worker and not runtime.worker.done():
            await runtime.stop();await asyncio.gather(runtime.worker,return_exceptions=True)
        await driver.close();await provider.close();store.close()

    app=FastAPI(title='CUA LAB',version=__version__,lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url=None)
    app.state.runtime=runtime;app.state.token=token;app.state.store=store
    origins={'http://127.0.0.1:8768','http://localhost:8768'}

    @app.middleware('http')
    async def local_security(request:Request,call_next):
        if request.headers.get('host','').split(':')[0] not in ('127.0.0.1','localhost','testserver'):
            return __import__('starlette.responses',fromlist=['JSONResponse']).JSONResponse({'detail':'Invalid host'},status_code=403)
        if request.headers.get('origin') and request.headers['origin'] not in origins:
            return __import__('starlette.responses',fromlist=['JSONResponse']).JSONResponse({'detail':'Invalid origin'},status_code=403)
        if request.url.path.startswith('/api/') and request.url.path!='/api/health':
            if not hmac.compare_digest(request.headers.get('x-cua-token',''),token):
                return __import__('starlette.responses',fromlist=['JSONResponse']).JSONResponse({'detail':'Local session authentication required'},status_code=401)
        response=await call_next(request)
        response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='no-referrer'
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob:; connect-src 'self' ws://127.0.0.1:8768 ws://localhost:8768; frame-ancestors 'none'; base-uri 'none'"
        return response

    @app.exception_handler(ValueError)
    async def bad_input(request,exc):
        from fastapi.responses import JSONResponse
        return JSONResponse({'detail':str(exc)},status_code=409)

    @app.get('/api/health')
    async def health():return {'application':'CUA LAB','version':__version__,'backend':'ready'}

    @app.get('/api/status')
    async def status():return {'version':__version__,'machine':profile,'runtime':runtime.snapshot(),'auto_sync':runtime.auto_sync,'model':provider.model}

    @app.post('/api/diagnostics')
    async def diagnostics():
        remote=await provider.health()
        driver_status={'ready':False,'detail':'Not checked while agent owns desktop'}
        if not runtime.worker or runtime.worker.done():
            try:
                observation=await driver.observe('health',fresh=True)
                driver_status={'ready':True,'version':driver.version,'desktop':bool(observation.get('windows')),'uia':bool(observation.get('window',{}).get('elements')),'detail':'Real window discovery completed'}
            except (DriverError,TimeoutError) as exc:driver_status={'ready':False,'detail':str(exc)}
        return {'openrouter':remote,'driver':driver_status,'database':'ready','knowledge_records':len(bank.shared)}

    @app.post('/api/tasks')
    async def start(body:TaskInput):return {'session':await runtime.start(**body.model_dump())}

    @app.post('/api/control/{control}')
    async def control(control:str):
        if control=='stop':await runtime.stop()
        elif control in ('pause','take-control'):runtime.pause()
        elif control=='resume':runtime.resume()
        else:raise HTTPException(404)
        return runtime.snapshot()

    @app.post('/api/approval')
    async def approval(body:ApprovalInput):
        runtime.resolve(body.plan_id,body.choice);return {'accepted':True}

    @app.get('/api/sessions')
    async def sessions():return store.sessions()

    @app.get('/api/sessions/{sid}')
    async def session(sid:str):return store.events(sid)

    @app.get('/api/images/{sid}/{name}')
    async def screenshot(sid:str,name:str):
        import re
        if not re.fullmatch(r'[a-f0-9]{32}|health',sid) or not re.fullmatch(r'[a-f0-9]{32}\.(png|jpg)',name):raise HTTPException(404)
        path=store.root/'sessions'/sid/'screenshots'/name
        if not path.is_file():raise HTTPException(404)
        return FileResponse(path)

    @app.get('/api/memory')
    async def memory():
        result=[]
        for r in store.learnings():
            record=Learning.model_validate({k:v for k,v in r.items() if k!='synced'})
            result.append({**r,'id':record.id,'confidence':record.confidence})
        return result

    @app.post('/api/memory/sync')
    async def sync():return {'synced':await bank.sync()}

    @app.post('/api/memory/refresh')
    async def refresh():
        try:return {'loaded':await bank.refresh()}
        except Exception:raise HTTPException(503,'Knowledge update unavailable; local cache preserved')

    @app.post('/api/memory/auto/{enabled}')
    async def auto(enabled:Literal['on','off']):
        runtime.auto_sync=enabled=='on';return {'enabled':runtime.auto_sync}

    @app.websocket('/ws')
    async def websocket(ws:WebSocket):
        if ws.headers.get('origin') not in origins:
            await ws.close(code=1008);return
        await ws.accept()
        try:
            auth=await asyncio.wait_for(ws.receive_json(),5)
            if not isinstance(auth.get('token'),str) or not hmac.compare_digest(auth['token'],token):
                await ws.close(code=1008);return
        except (TimeoutError,ValueError,WebSocketDisconnect):
            await ws.close();return
        q=asyncio.Queue(maxsize=256);runtime.subscribers.add(q)
        try:
            await ws.send_json({'type':'snapshot','data':runtime.snapshot()})
            while True:
                try:event=await asyncio.wait_for(q.get(),15)
                except TimeoutError:event={'type':'heartbeat','data':runtime.snapshot()}
                await ws.send_json(event)
        except (WebSocketDisconnect,RuntimeError):pass
        finally:runtime.subscribers.discard(q)

    static=Path(__file__).parent/'static'
    app.mount('/static',StaticFiles(directory=static),name='static')
    @app.get('/')
    async def index():return FileResponse(static/'index.html')
    return app
