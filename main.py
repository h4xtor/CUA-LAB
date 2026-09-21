"""Windows native launcher; smoke mode tests packaging without GUI control."""
import argparse
import os
import secrets
import socket
import sys
import threading
import time
import urllib.request


class NativeDialogs:
    def choose_gguf(self):
        import webview
        selected=webview.windows[0].create_file_dialog(webview.OPEN_DIALOG,allow_multiple=False,file_types=('GGUF model (*.gguf)',))
        return selected[0] if selected else None


def report_startup_failure(exc, interactive=True):
    import traceback
    from cua_lab.privacy import redact
    from cua_lab.store import data_dir
    folder = data_dir() / 'logs'
    folder.mkdir(parents=True, exist_ok=True)
    log = folder / 'startup.log'
    with log.open('a', encoding='utf-8') as output:
        output.write(time.strftime('%Y-%m-%d %H:%M:%S') + '\n' + redact(''.join(traceback.format_exception(exc))) + '\n')
    message = f'CUA LAB startup failed: {type(exc).__name__}. Details: {log}'
    if os.name == 'nt' and interactive:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, message, 'CUA LAB', 0x10)
    elif sys.stderr is not None:
        print(message, file=sys.stderr)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--smoke-test', action='store_true')
    parser.add_argument('--browser', action='store_true')
    args = parser.parse_args()
    if os.name == 'nt':
        import ctypes
        try:
            ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        except (AttributeError, OSError):
            pass
    if os.name != 'nt' and not (args.smoke_test or args.browser):
        raise RuntimeError('Windows required')
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if os.name == 'nt':
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    try:
        listener.bind(('127.0.0.1', 8768))
    except OSError:
        message = 'CUA LAB is already running, or port 8768 is occupied.'
        if os.name == 'nt' and not args.smoke_test:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, message, 'CUA LAB', 0)
        else:
            print(message)
        return 1
    listener.listen(128)
    import uvicorn
    from cua_lab.server import create_app
    token = secrets.token_urlsafe(32)
    app = create_app(token=token)
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=8768, log_level='warning', access_log=False, use_colors=False, timeout_graceful_shutdown=5, loop='asyncio'))
    thread = threading.Thread(target=lambda: server.run(sockets=[listener]), name='cua-backend', daemon=True)
    thread.start()
    try:
        deadline = time.monotonic()+20
        while not server.started:
            if not thread.is_alive() or time.monotonic()>deadline:
                raise RuntimeError('Backend startup failed')
            time.sleep(.05)
        url = 'http://127.0.0.1:8768/#'+token
        if args.smoke_test:
            import json
            with urllib.request.urlopen('http://127.0.0.1:8768/api/health', timeout=5) as response:
                assert json.load(response)['application'] == 'CUA LAB'
            request = urllib.request.Request('http://127.0.0.1:8768/api/status', headers={'X-Cua-Token': token})
            with urllib.request.urlopen(request, timeout=5) as response:
                assert json.load(response)['runtime']['status'] == 'idle'
            for path in ('/', '/static/app.js', '/static/style.css'):
                with urllib.request.urlopen('http://127.0.0.1:8768'+path, timeout=5) as response:
                    assert response.read(), f'Empty packaged resource: {path}'
            (app.state.store.root / 'smoke-test.json').write_text(json.dumps({'status':'passed','checks':['backend','authenticated_status','sqlite','static_resources']}), encoding='utf-8')
            print('PASS: resources, backend, authenticated status, SQLite initialization')
        elif args.browser:
            import webbrowser
            webbrowser.open(url)
            print('CUA LAB running at http://127.0.0.1:8768 — Ctrl+C to exit')
            while thread.is_alive():
                time.sleep(.2)
        else:
            import webview
            webview.create_window('CUA LAB', url, width=1440, height=1000, min_size=(900, 700), background_color='#0c1016', js_api=NativeDialogs())
            webview.start(gui='edgechromium', private_mode=True)
    except KeyboardInterrupt:
        pass
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        listener.close()
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        report_startup_failure(exc, interactive='--smoke-test' not in sys.argv)
        sys.exit(1)
