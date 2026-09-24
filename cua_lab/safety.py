"""Fail closed: unknown GUI effects require one-shot approval."""
import json
import re
from .protocol import READ_TOOLS
from .privacy import sensitive_state, redact

RISK = re.compile(r'(?i)delete|remove|uninstall|install|format|shutdown|reboot|restart|registry|firewall|service|payment|purchase|buy|transfer|upload|password|credential|sign.?in|log.?in|administrator|elevat|slet|betal|køb|adgangskode')
CALC = re.compile(r'(?i)calculator|lommeregner')

def classify(action, observation, read_only=False):
    tool, args = action['tool'], action['arguments']
    if tool in READ_TOOLS:
        return None
    if read_only:
        raise PermissionError('Read-only mode prohibits desktop mutations')
    if sensitive_state(observation):
        return 'Sensitive interface: use Take Control for credentials; this action requires review.'
    if redact(args) != args:
        raise PermissionError('Credential-like text is not accepted; enter it manually using Take Control')
    combined = json.dumps(args, ensure_ascii=False)
    if RISK.search(combined):
        return 'Potential system, data, authentication or financial effect'
    state = observation.get('window', {})
    app = str(state.get('app_name', '')) + ' ' + str(state.get('window_title', ''))
    target = args.get('target', args)
    exact = target.get('pid') == state.get('pid') and target.get('window_id') == state.get('window_id') and state.get('pid') is not None
    if tool == 'launch_app' and args.get('name') in ('Calculator', 'Chrome', 'Microsoft Edge'):
        return None
    if exact and CALC.search(app):
        if tool == 'type_text' and re.fullmatch(r'[0-9 .+*/=()\-]{1,80}', args.get('text', '')):
            return None
        if tool == 'press_key' and args.get('key', '').lower() in ('enter', 'escape', 'esc', 'backspace', *list('0123456789+-*/=.')) and not args.get('modifiers'):
            return None
        if tool == 'click' and args.get('element_token'):
            element = next((e for e in state.get('elements', []) if e.get('element_token') == args['element_token']), None)
            if element and not RISK.search(json.dumps(element)):
                label = str(element.get('label', '')).lower()
                if re.fullmatch(r'[0-9 .+*/=()\-]+', label) or label in {'one','two','three','four','five','six','seven','eight','nine','zero','equals','multiply by','plus','minus','divide by','clear','clear entry','et','en','to','tre','fire','fem','seks','syv','otte','ni','nul','lig med','er lig med','gang med','multiplicer med','divider med','ryd','ryd post'}:
                    return None
    if exact and re.search(r'(?i)chrome|edge|chromium', app):
        if tool == 'hotkey' and [k.lower() for k in args.get('keys', [])] in (['ctrl','l'], ['control','l']):
            return None
    return 'Unknown GUI effect: approve this exact action once. Model safety claims do not override this gate.'
