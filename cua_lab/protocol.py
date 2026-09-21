"""Runtime model contract. Model output never becomes a shell command."""
import copy
from typing import Literal
import jsonschema
from pydantic import BaseModel, ConfigDict, Field, model_validator

READ_TOOLS = frozenset({'list_windows', 'list_apps', 'get_window_state', 'get_desktop_state'})
ALLOWED_FIELDS = {
    'list_windows': {'pid', 'on_screen_only'}, 'list_apps': set(),
    'get_window_state': {'pid', 'window_id', 'max_depth', 'max_elements', 'query'},
    'get_desktop_state': set(),
    'click': {'target', 'pid', 'window_id', 'element_token', 'x', 'y', 'button', 'count', 'delivery_mode'},
    'hotkey': {'target', 'pid', 'window_id', 'keys', 'delivery_mode'},
    'press_key': {'target', 'pid', 'window_id', 'key', 'modifiers', 'delivery_mode'},
    'type_text': {'target', 'pid', 'window_id', 'text', 'element_token', 'delivery_mode'},
    'scroll': {'target', 'pid', 'window_id', 'x', 'y', 'direction', 'amount', 'by', 'delivery_mode'},
    'bring_to_front': {'pid', 'window_id'},
    'launch_app': {'name'},
}

class Action(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    tool: str
    arguments: dict

class Decision(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    status: Literal['continue', 'completed', 'needs_approval', 'blocked', 'failed']
    observation: str = Field(max_length=1600)
    user_message: str = Field(max_length=1600)
    action: Action | None
    expected_result: str = Field(max_length=1000)
    requires_approval: bool
    evidence: str = Field(max_length=1600)

    @model_validator(mode='after')
    def consistent(self):
        if self.status in ('continue', 'needs_approval') and self.action is None:
            raise ValueError('An executable state needs an action')
        if self.status in ('completed', 'blocked', 'failed') and self.action is not None:
            raise ValueError('Terminal states cannot contain actions')
        if self.status == 'completed' and not self.evidence.strip():
            raise ValueError('Completion requires observable evidence')
        return self

class Verification(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    satisfied: bool
    evidence: str = Field(min_length=1, max_length=1600)

def public_schemas(tools):
    result = {}
    for tool in tools:
        name = tool['name']
        if name not in ALLOWED_FIELDS:
            continue
        schema = copy.deepcopy(tool['inputSchema'])
        schema['properties'] = {k: v for k, v in schema.get('properties', {}).items() if k in ALLOWED_FIELDS[name]}
        schema['additionalProperties'] = False
        # If a driver version requires an unsupported field, disable that tool.
        if not set(schema.get('required', [])) <= set(schema['properties']):
            continue
        if name == 'launch_app':
            schema = {'type': 'object', 'properties': {'name': {'enum': ['Calculator', 'Chrome', 'Microsoft Edge']}}, 'required': ['name'], 'additionalProperties': False}
        result[name] = schema
    return result

def validate_action(action, schemas):
    parsed = Action.model_validate(action)
    if parsed.tool not in ALLOWED_FIELDS or parsed.tool not in schemas:
        raise ValueError('Unknown or unavailable tool')
    if not set(parsed.arguments) <= ALLOWED_FIELDS[parsed.tool]:
        raise ValueError('Unsupported argument')
    try:
        jsonschema.Draft202012Validator(schemas[parsed.tool]).validate(parsed.arguments)
    except jsonschema.ValidationError as exc:
        raise ValueError('Invalid tool argument shape') from exc
    a = parsed.arguments
    if 'text' in a and (not isinstance(a['text'], str) or len(a['text']) > 4000):
        raise ValueError('Text exceeds 4000 characters')
    if 'max_elements' in a and not 1 <= a['max_elements'] <= 150:
        raise ValueError('max_elements must be 1..150')
    if 'max_depth' in a and not 1 <= a['max_depth'] <= 12:
        raise ValueError('max_depth must be 1..12')
    if 'target' in a:
        target = a['target']
        expected = {'kind', 'pid', 'window_id'} if target.get('kind') == 'window' else {'kind', 'display_id'}
        if set(target) != expected or target.get('kind') not in ('window', 'desktop'):
            raise ValueError('Invalid exact target')
        if target.get('kind') == 'desktop' and target['display_id'] != 'primary':
            raise ValueError('Driver desktop input supports primary display only; use a window target')
    return parsed.model_dump()
