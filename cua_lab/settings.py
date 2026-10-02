"""Model backend settings. Secrets are never stored here; only env-var references."""
import json
import os
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

PROVIDERS = ('openrouter', 'openai', 'gguf')
# The only environment variables a provider may read a key from.
KEY_ENVS = ('OPENROUTER_API_KEY', 'CUA_LAB_API_KEY', 'OPENAI_API_KEY')
DEFAULT_MODELS = {'openrouter': 'qwen/qwen3.7-flash', 'openai': 'gpt-4.1-mini', 'gguf': 'local-gguf'}

class ProviderSettings(BaseModel):
    model_config = ConfigDict(extra='forbid')
    provider: Literal['openrouter', 'openai', 'gguf'] = 'openrouter'
    model: str = Field(default='', max_length=200)
    # OpenAI-compatible endpoint: OpenAI, Groq, LM Studio, Ollama, llama-server, vLLM ...
    base_url: str = Field(default='https://api.openai.com/v1', max_length=500)
    # Local GGUF via llama.cpp's llama-server.
    gguf_path: str = Field(default='', max_length=1000)
    mmproj_path: str = Field(default='', max_length=1000)
    llama_server_path: str = Field(default='', max_length=1000)
    context_size: int = Field(default=16384, ge=2048, le=262144)
    gpu_layers: int = Field(default=99, ge=0, le=999)

    @field_validator('base_url')
    @classmethod
    def http_only(cls, value):
        value = value.strip().rstrip('/')
        if not value.startswith(('http://', 'https://')):
            raise ValueError('base_url must start with http:// or https://')
        return value

    @field_validator('model', 'gguf_path', 'mmproj_path', 'llama_server_path')
    @classmethod
    def strip(cls, value):
        return value.strip().strip('"')

    @property
    def model_name(self):
        return self.model or DEFAULT_MODELS[self.provider]

def from_env():
    env = {
        'provider': os.getenv('CUA_LAB_PROVIDER', '').strip().lower() or 'openrouter',
        'model': os.getenv('CUA_LAB_MODEL', ''),
        'base_url': os.getenv('CUA_LAB_BASE_URL', '') or 'https://api.openai.com/v1',
        'gguf_path': os.getenv('CUA_LAB_GGUF_PATH', ''),
        'mmproj_path': os.getenv('CUA_LAB_MMPROJ_PATH', ''),
        'llama_server_path': os.getenv('LLAMA_SERVER_PATH', ''),
    }
    if env['provider'] not in PROVIDERS:
        env['provider'] = 'openrouter'
    if env['gguf_path'] and not os.getenv('CUA_LAB_PROVIDER'):
        env['provider'] = 'gguf'
    try:
        return ProviderSettings.model_validate(env)
    except ValueError:
        return ProviderSettings()

def load(store):
    row = store.db.execute("SELECT value FROM settings WHERE key='provider'").fetchone()
    if row:
        try:
            return ProviderSettings.model_validate(json.loads(row['value']))
        except ValueError:
            pass
    return from_env()

def save(store, settings):
    store.db.execute("INSERT INTO settings VALUES('provider',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (settings.model_dump_json(),))
    store.db.commit()
