"""Private provider settings. Windows protects saved keys for the current user."""
import base64
import ctypes
import ipaddress
import json
import os
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProviderSettings(BaseModel):
    model_config = ConfigDict(extra='forbid')
    provider: Literal['openrouter', 'ollama', 'lmstudio'] = 'openrouter'
    model: str = Field(default='', max_length=200)
    base_url: str = 'http://127.0.0.1:11434'
    allow_paid: bool = False

    @field_validator('model')
    @classmethod
    def valid_model(cls, value):
        if any(c.isspace() for c in value) or any(ord(c) < 32 for c in value):
            raise ValueError('Model ID cannot contain whitespace')
        return value

    @field_validator('base_url')
    @classmethod
    def local_url(cls, value):
        url = urlsplit(value)
        try:
            loopback = url.hostname == 'localhost' or ipaddress.ip_address(url.hostname or '').is_loopback
        except ValueError:
            loopback = False
        if not loopback or url.scheme != 'http' or url.username or url.password or url.query or url.fragment or url.path not in ('', '/'):
            raise ValueError('Local engine URL must be an HTTP loopback address without a path')
        if not url.port:
            raise ValueError('Local engine URL must include a port')
        return value.rstrip('/')


def protect_key(value, decrypt=False):
    if os.name != 'nt':
        raise ValueError('Saving API keys requires Windows; use OPENROUTER_API_KEY on other systems')
    from ctypes import wintypes
    class Blob(ctypes.Structure):
        _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]
    raw = base64.b64decode(value, validate=True) if decrypt else value.encode('utf-8')
    buffer = ctypes.create_string_buffer(raw)
    source = Blob(len(raw), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    result = Blob()
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    fn = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    fn.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    fn.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    if not fn(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(result)):
        raise ValueError('Windows could not protect or unlock the saved API key')
    try:
        data = ctypes.string_at(result.data, result.size)
        return data.decode('utf-8') if decrypt else base64.b64encode(data).decode('ascii')
    finally:
        kernel.LocalFree(result.data)


class Configuration:
    def __init__(self, root):
        self.path = Path(root)/'provider.json'
        self.encrypted_key = ''
        self.api_key = ''
        self.settings = ProviderSettings(model=os.getenv('CUA_LAB_MODEL', 'qwen/qwen3.7-flash'))
        if self.path.is_file():
            data = json.loads(self.path.read_text(encoding='utf-8'))
            self.settings = ProviderSettings.model_validate(data['settings'])
            self.encrypted_key = data.get('protected_openrouter_key', '')
            if self.encrypted_key:
                self.api_key = protect_key(self.encrypted_key, decrypt=True)

    def public(self):
        return {**self.settings.model_dump(), 'api_key_configured':bool(self.api_key or os.getenv('OPENROUTER_API_KEY'))}

    def save(self, settings, api_key=None, clear_key=False):
        encrypted = self.encrypted_key
        key = self.api_key
        if clear_key:
            encrypted = key = ''
        elif api_key:
            if len(api_key) > 512 or any(c.isspace() for c in api_key):
                raise ValueError('Invalid API key format')
            encrypted = protect_key(api_key)
            key = api_key
        data = {'settings':settings.model_dump(), 'protected_openrouter_key':encrypted}
        temporary = self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps(data, indent=2), encoding='utf-8')
        temporary.replace(self.path)
        self.settings, self.encrypted_key, self.api_key = settings, encrypted, key
