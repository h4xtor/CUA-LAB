import os
import re

SECRET = re.compile(r'(?i)(?:sk-(?:or-v1-)?[a-z0-9_-]{12,}|gh[pousr]_[a-z0-9_]{12,}|github_pat_[a-z0-9_]{12,}|bearer\s+[a-z0-9._-]{12,}|(?:password|api[_ -]?key|access[_ -]?token)\s*[:=]\s*\S+)')

def redact(value):
    if isinstance(value, dict):
        descriptor = ' '.join(str(value.get(k, '')) for k in ('label', 'role', 'name')).lower()
        if value.get('is_password') or any(x in descriptor for x in ('password','adgangskode','api key','api_key','secret key')):
            return {'role': 'sensitive_element', 'label': '[REDACTED]', 'value': '[REDACTED]'}
        return {k: ('[REDACTED]' if k.lower() in {'password', 'api_key', 'authorization', 'cookie'} else redact(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, str):
        for name in ('OPENROUTER_API_KEY', 'CUA_LAB_GITHUB_TOKEN'):
            key = os.getenv(name)
            if key:
                value = value.replace(key, '[REDACTED]')
        return SECRET.sub('[REDACTED]', value)
    return value

def sensitive_state(state):
    import json
    text = json.dumps(state, ensure_ascii=False).lower()
    return any(s in text for s in ('password', 'passwd', 'adgangskode', 'api key', 'api_key', 'secret key', 'credit card', 'kortnummer'))
