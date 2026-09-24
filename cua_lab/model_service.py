"""One stable runtime provider, replaced only while no task is active."""
import httpx
from pathlib import Path

from .configuration import Configuration
from .local_models import LocalModels
from .privacy import register_private_key
from .provider import OpenRouterProvider, LocalProvider, GGUFProvider


class ModelService:
    def __init__(self, root):
        self.root=root
        self.config=Configuration(root)
        self.local=LocalModels(root)
        self.current=self.build(self.config.settings)

    def build(self, settings):
        register_private_key(self.config.api_key)
        if settings.provider=='openrouter':
            return OpenRouterProvider(self.root,model=settings.model,api_key=self.config.api_key,allow_paid=settings.allow_paid)
        if settings.provider=='gguf':
            return GGUFProvider(self.root,settings)
        return LocalProvider(self.root,settings,self.local)

    @property
    def model(self): return self.current.model

    @property
    def label(self): return self.current.label

    async def decide(self, *args, **kwargs): return await self.current.decide(*args, **kwargs)
    async def verify(self, *args, **kwargs): return await self.current.verify(*args, **kwargs)
    async def health(self): return await self.current.health()

    async def save(self, settings, api_key=None, clear_key=False):
        if settings.provider=='gguf':
            path=Path(settings.gguf_path)
            if not settings.gguf_path or not path.is_absolute() or not path.is_file():
                raise ValueError('Select an existing local .gguf file')
            with path.open('rb') as stream:
                if stream.read(4)!=b'GGUF':
                    raise ValueError('The selected file is not a GGUF model')
            if settings.gguf_mmproj:
                mmproj=Path(settings.gguf_mmproj)
                if not mmproj.is_absolute() or not mmproj.is_file():
                    raise ValueError('Select an existing local vision (mmproj) .gguf file, or leave it blank')
            settings=settings.model_copy(update={'model':path.stem})
        elif not settings.model:
            raise ValueError('Choose a model before saving')
        elif settings.provider!='openrouter':
            await self.local.check_model(settings)
        self.config.save(settings,api_key,clear_key)
        previous=self.current
        self.current=self.build(settings)
        await previous.close()
        return self.config.public()

    async def models(self, settings):
        if settings.provider=='gguf': return []
        if settings.provider!='openrouter': return await self.local.models(settings)
        async with httpx.AsyncClient(timeout=15,follow_redirects=False) as client:
            try:
                response=await client.get('https://openrouter.ai/api/v1/models')
                response.raise_for_status()
                return [{'id':r['id'],'name':r.get('name',r['id']),'pricing':r.get('pricing',{})} for r in response.json()['data']]
            except (httpx.HTTPError,ValueError,KeyError) as exc:
                raise ValueError('OpenRouter model catalog unavailable') from exc

    async def close(self):
        await self.current.close()
        await self.local.close()
