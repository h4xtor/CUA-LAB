"""Explicit local model discovery/load/import; never downloads a model."""
import asyncio
import json
import os
import re
import shutil
import tempfile
from pathlib import Path

import httpx

from .configuration import ProviderSettings


class LocalModels:
    def __init__(self, root=None):
        self.process = None
        self.lock = asyncio.Lock()
        self.root=Path(root) if root else Path(tempfile.mkdtemp(prefix='cua-local-engine-'))
        (self.root/'logs').mkdir(parents=True,exist_ok=True)
        self.log_path=self.root/'logs/local-engine.log'

    async def request(self, settings, method, path, body=None, timeout=15):
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=3), trust_env=False, follow_redirects=False) as client:
            try:
                response = await client.request(method, settings.base_url+path, json=body)
                if not response.is_success:
                    raise ValueError(f'Local engine HTTP {response.status_code}; check that the model and server are available')
                return response.json()
            except (httpx.HTTPError, json.JSONDecodeError) as exc:
                raise ValueError('Local engine unavailable or returned an invalid response') from exc

    async def models(self, settings):
        if settings.provider == 'openrouter':
            raise ValueError('Select a local engine first')
        data = await self.request(settings, 'GET', '/api/tags' if settings.provider == 'ollama' else '/v1/models')
        rows = data.get('models', []) if settings.provider == 'ollama' else data.get('data', [])
        return [{'id':r.get('name') or r.get('id'), 'size':r.get('size')} for r in rows if r.get('name') or r.get('id')]

    async def check_model(self, settings):
        if settings.model not in {r['id'] for r in await self.models(settings)}:
            raise ValueError('Select an installed model from Refresh models; no automatic downloads')
        if settings.provider == 'ollama':
            data = await self.request(settings, 'POST', '/api/show', {'model':settings.model})
            if data.get('remote_host') or data.get('remote_model') or settings.model.endswith('-cloud'):
                raise ValueError('Cloud models are not accepted by the local-only provider')
            if 'completion' not in data.get('capabilities', []):
                raise ValueError('This model does not support text generation')
            return data
        return {}

    async def load(self, settings):
        await self.check_model(settings)
        if settings.provider == 'ollama':
            await self.request(settings, 'POST', '/api/generate', {'model':settings.model,'stream':False,'keep_alive':'10m'}, timeout=180)
        else:
            await self.request(settings, 'POST', '/api/v1/models/load', {'model':settings.model}, timeout=180)
        return {'detail':'Model loaded; inference has not yet been tested'}

    def executable(self):
        binary = shutil.which('ollama')
        candidate = Path(os.getenv('LOCALAPPDATA', ''))/'Programs/Ollama/ollama.exe'
        if not binary and candidate.is_file():
            binary = str(candidate)
        if not binary:
            raise ValueError('Ollama is not installed. Install Ollama to run or import GGUF models.')
        return binary

    async def start(self, settings):
        if settings.provider != 'ollama':
            raise ValueError('Start LM Studio and enable its local server there')
        async with self.lock:
            try:
                await self.models(settings)
                return {'detail':'Ollama is already running'}
            except ValueError:
                pass
            if self.process and self.process.returncode is None:
                raise ValueError('The app-owned Ollama server is already starting or uses a different port')
            env = {k:v for k,v in os.environ.items() if k not in ('OPENROUTER_API_KEY','CUA_LAB_GITHUB_TOKEN')}
            env['OLLAMA_HOST'] = settings.base_url
            env['OLLAMA_NO_CLOUD'] = '1'
            with self.log_path.open('ab') as log:
                self.process = await asyncio.create_subprocess_exec(self.executable(), 'serve', env=env,
                    stdout=log, stderr=log, creationflags=0x08000000 if os.name == 'nt' else 0)
            try:
                async with asyncio.timeout(20):
                    while self.process.returncode is None:
                        try:
                            await self.models(settings)
                            return {'detail':'Local Ollama engine started'}
                        except ValueError:
                            await asyncio.sleep(.25)
                raise ValueError(f'Ollama exited during startup. Details: {self.log_path}')
            except TimeoutError as exc:
                await self.close()
                raise ValueError('Ollama startup timed out') from exc

    async def import_gguf(self, settings, path, name):
        if settings.provider != 'ollama':
            raise ValueError('Choose Ollama to import a local GGUF file')
        source = Path(path)
        if not source.is_absolute() or source.suffix.lower() != '.gguf' or not source.is_file() or any(c in path for c in ('\n','\r','"')):
            raise ValueError('Select an existing local .gguf file')
        with source.open('rb') as stream:
            if stream.read(4) != b'GGUF':
                raise ValueError('The selected file is not a GGUF model')
        if not re.fullmatch(r'cua-[a-z0-9][a-z0-9._-]{0,70}', name):
            raise ValueError('Import name must start with cua- and contain lowercase letters, numbers, dots or dashes')
        async with self.lock:
            existing = {r['id'].removesuffix(':latest') for r in await self.models(settings)}
            if name in existing:
                raise ValueError('That model name already exists; choose a new name')
            with tempfile.TemporaryDirectory(prefix='cua-model-import-') as directory:
                modelfile = Path(directory)/'Modelfile'
                modelfile.write_text('FROM "'+source.as_posix()+'"\n', encoding='utf-8')
                env = {k:v for k,v in os.environ.items() if k not in ('OPENROUTER_API_KEY','CUA_LAB_GITHUB_TOKEN')}
                env['OLLAMA_HOST'] = settings.base_url
                with self.log_path.open('ab') as log:
                    process = await asyncio.create_subprocess_exec(self.executable(), 'create', name, '-f', str(modelfile), env=env,
                        stdout=log, stderr=log, creationflags=0x08000000 if os.name == 'nt' else 0)
                try:
                    async with asyncio.timeout(600):
                        code = await process.wait()
                    if code:
                        raise ValueError(f'GGUF import failed; source preserved. Details: {self.log_path}')
                finally:
                    if process.returncode is None:
                        process.kill()
                        await process.wait()
            if name not in {r['id'].removesuffix(':latest') for r in await self.models(settings)}:
                raise ValueError('Import completed without an installed model; refresh the engine')
            return {'model':name+':latest','detail':'GGUF imported locally. Select the model and save to use it.'}

    async def close(self):
        if self.process and self.process.returncode is None:
            if os.name=='nt':
                # Ollama runners outlive a terminated parent on Windows unless
                # its owned process tree is explicitly closed as well.
                killer=await asyncio.create_subprocess_exec(
                    str(Path(os.environ['SystemRoot'])/'System32/taskkill.exe'),
                    '/PID',str(self.process.pid),'/T','/F',
                    stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL,
                    creationflags=0x08000000)
                try:
                    await asyncio.wait_for(killer.wait(),10)
                except TimeoutError:
                    killer.kill()
                    await killer.wait()
                    raise ValueError('Timed out stopping the app-owned Ollama process tree')
            else:
                self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), 5)
            except TimeoutError:
                self.process.kill()
                await self.process.wait()
