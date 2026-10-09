"""Optional browser test: run explicitly with CUA_UI_TEST=1 and Playwright installed."""
import os
import threading
import time
import pytest

@pytest.mark.skipif(os.getenv('CUA_UI_TEST')!='1',reason='Optional local browser test')
def test_real_browser_layout_health_and_failed_task(tmp_path, monkeypatch):
    import uvicorn
    import socket
    from playwright.sync_api import sync_playwright, expect
    from cua_lab.server import create_app
    from cua_lab.driver import CuaDriverController, DriverError
    from cua_lab.model_service import ModelService
    class UnavailableDriver(CuaDriverController):
        async def observe(self, sid, fresh=False,capture=True):
            raise DriverError('Acceptance fixture: driver unavailable')
    monkeypatch.delenv('OPENROUTER_API_KEY', raising=False)
    provider=ModelService(tmp_path)
    async def capabilities():return False
    provider.supports_vision=capabilities
    async def installed_models(settings):return [{'id':'qwen2.5vl:7b'},{'id':'gemma3:4b'}]
    provider.local.models=installed_models
    async def installed_metadata(settings):return {'capabilities':['completion','vision']}
    provider.local.check_model=installed_metadata
    app=create_app(tmp_path,token='browser-test-token',driver=UnavailableDriver(tmp_path),provider=provider)
    listener=socket.socket();listener.bind(('127.0.0.1',0))
    port=listener.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=port,log_level='error',access_log=False))
    thread=threading.Thread(target=lambda:server.run(sockets=[listener]),daemon=True);thread.start()
    deadline=time.monotonic()+10
    while not server.started:
        assert time.monotonic()<deadline
        time.sleep(.05)
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
            page=browser.new_page(viewport={'width':1440,'height':1100})
            errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(f'http://127.0.0.1:{port}/#browser-test-token')
            expect(page.locator('#connection')).to_have_text('LIVE')
            expect(page.locator('#quick-model option')).to_have_count(2)
            page.locator('#quick-model-menu summary').click()
            page.locator('#quick-model').select_option('qwen2.5vl:7b')
            page.locator('#quick-model-save').click()
            expect(page.locator('#model')).to_contain_text('qwen2.5vl:7b')
            if os.getenv('CUA_UI_CAPTURE_DIR'):
                from pathlib import Path
                preview=Path(os.environ['CUA_UI_CAPTURE_DIR']);preview.mkdir(parents=True,exist_ok=True)
                page.set_viewport_size({'width':1440,'height':900})
                page.screenshot(path=str(preview/'ready-1440.png'),full_page=True)
            screen=page.locator('.desktop').bounding_box()
            task=page.locator('.task').bounding_box()
            log=page.locator('.timeline').bounding_box()
            assert screen['x']<task['x'] and log['y']>screen['y']+screen['height']-2
            assert page.locator('[data-control=stop]').is_visible()
            page.locator('[data-tab=models]').click()
            expect(page.locator('#provider-choice')).to_have_value('ollama')
            page.locator('#provider-choice').select_option('ollama')
            expect(page.locator('#engine-url')).to_have_value('http://127.0.0.1:11434')
            expect(page.locator('#gguf-settings')).to_be_visible()
            page.locator('#provider-choice').select_option('lmstudio')
            expect(page.locator('#engine-url')).to_have_value('http://127.0.0.1:1234')
            expect(page.locator('#gguf-settings')).to_be_hidden()
            page.locator('#provider-choice').select_option('openrouter')
            page.locator('#model-id').fill('openrouter/free')
            page.locator('#model-form button[type=submit]').click()
            expect(page.locator('#model-status')).to_have_text('Connection saved')
            expect(page.locator('#model')).to_contain_text('openrouter/free')
            page.locator('[data-tab=workspace]').click()
            page.locator('#prompt').fill('Inspect desktop read-only')
            page.locator('#start').click()
            expect(page.locator('#state')).to_have_text('FAILED')
            expect(page.locator('#phase')).to_contain_text('failed')
            expect(page.locator('#phase-detail')).to_contain_text('Task failed')
            assert page.locator('#vision').count()==0
            expect(page.locator('#vision-label')).to_contain_text('automatic')
            expect(page.locator('#events .event').first).to_be_visible()
            assert 'Acceptance fixture: driver unavailable' in page.locator('#notice').inner_text()
            expect(page.locator('#chat-messages')).to_contain_text('Inspect desktop read-only')
            expect(page.locator('#chat-messages')).to_contain_text('Acceptance fixture: driver unavailable')
            page.locator('[data-tab=memory]').click()
            assert page.locator('#learnings').is_visible()
            page.locator('[data-tab=history]').click()
            page.locator('#sessions button').first.click()
            expect(page.locator('#replay .event').first).to_be_visible()
            page.locator('[data-tab=workspace]').click()
            # Reopening the UI restores all durable events, including those
            # missed while disconnected. Scrolling back must stay possible.
            sid=app.state.runtime.sid
            for i in range(300):
                app.state.store.event(sid,i,'audit_event',{'message':f'Persistent event {i}'})
            total=len(app.state.store.events(sid))
            page.reload()
            try:expect(page.locator('#events .event')).to_have_count(total)
            except AssertionError:
                print('Recovery diagnostics:',page.locator('#notice').inner_text(),page.locator('#connection').inner_text(),errors)
                raise
            expect(page.locator('#events')).to_contain_text('Persistent event 0')
            expect(page.locator('#events')).to_contain_text('Persistent event 299')
            capture_dir=tmp_path
            if os.getenv('CUA_UI_CAPTURE_DIR'):
                from pathlib import Path
                capture_dir=Path(os.environ['CUA_UI_CAPTURE_DIR'])
                capture_dir.mkdir(parents=True,exist_ok=True)
            for width,height in ((900,700),(1024,768),(1280,720),(1440,900),(760,1000),(390,844),(760,580),(390,550)):
                page.set_viewport_size({'width':width,'height':height})
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                for selector in ('[data-control=stop]','#start','#prompt'):
                    control=page.locator(selector).bounding_box()
                    assert 0<=control['y'] and control['y']+control['height']<=height, (width,height,selector,control)
                assert page.locator('.task').evaluate('(el)=>el.scrollHeight<=el.clientHeight+2'), (width,height,page.locator('.task').evaluate('(el)=>[el.scrollHeight,el.clientHeight]'))
                if width<900:
                    chat=page.locator('.task').bounding_box();desktop=page.locator('.desktop').bounding_box()
                    assert desktop['y']>=chat['y']+chat['height']-1
                if width in (900,1440,390):page.screenshot(path=str(capture_dir/f'workspace-{width}-{height}.png'),full_page=True)
            page.set_viewport_size({'width':900,'height':700})
            page.locator('.task-details summary').click()
            expect(page.locator('#verification')).to_be_visible()
            page.keyboard.press('Escape')
            expect(page.locator('.task-details')).not_to_have_attribute('open','')
            page.locator('[data-control=stop]').focus()
            expect(page.locator('[data-control=stop]')).to_be_focused()
            page.screenshot(path=str(tmp_path/'cua-lab-ui.png'),full_page=True)
            page.set_viewport_size({'width':760,'height':1000})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            assert errors==[]
            browser.close()
    finally:
        server.should_exit=True;thread.join(10)
