"""One stable runtime provider, replaced only while no task is active."""
import httpx

from .configuration import Configuration
from .local_models import LocalModels
from .privacy import register_private_key
from .provider import OpenRouterProvider, LocalProvider


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
        return LocalProvider(self.root,settings,self.local)

    @property
    def model(self): return self.current.model

    @property
    def label(self): return self.current.label

    async def decide(self, *args, **kwargs): return await self.current.decide(*args, **kwargs)
    async def verify(self, *args, **kwargs): return await self.current.verify(*args, **kwargs)
    async def health(self): return await self.current.health()

    async def save(self, settings, api_key=None, clear_key=False):
        if not settings.model:
            raise ValueError('Choose a model before saving')
        if settings.provider!='openrouter':
            await self.local.check_model(settings)
        self.config.save(settings,api_key,clear_key)
        previous=self.current
        self.current=self.build(settings)
        await previous.close()
        return self.config.public()

    async def models(self, settings):
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
