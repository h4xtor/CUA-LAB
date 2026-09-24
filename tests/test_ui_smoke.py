"""Optional browser test: run explicitly with CUA_UI_TEST=1 and Playwright installed."""
import os
import threading
import time
import pytest

@pytest.mark.skipif(os.getenv('CUA_UI_TEST')!='1',reason='Optional local browser test')
def test_real_browser_layout_health_and_failed_task(tmp_path, monkeypatch):
    import uvicorn
    from playwright.sync_api import sync_playwright, expect
    from cua_lab.server import create_app
    from cua_lab.driver import CuaDriverController, DriverError
    from cua_lab.model_service import ModelService
    class UnavailableDriver(CuaDriverController):
        async def observe(self, sid, fresh=False):
            raise DriverError('Acceptance fixture: driver unavailable')
    monkeypatch.delenv('OPENROUTER_API_KEY', raising=False)
    provider=ModelService(tmp_path)
    async def installed_models(settings):return [{'id':'qwen2.5vl:7b'},{'id':'gemma3:4b'}]
    provider.local.models=installed_models
    app=create_app(tmp_path,token='browser-test-token',driver=UnavailableDriver(tmp_path),provider=provider)
    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8768,log_level='error',access_log=False))
    thread=threading.Thread(target=server.run,daemon=True);thread.start()
    deadline=time.monotonic()+10
    while not server.started:
        assert time.monotonic()<deadline
        time.sleep(.05)
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
            page=browser.new_page(viewport={'width':1440,'height':1100})
            errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto('http://127.0.0.1:8768/#browser-test-token')
            expect(page.locator('#connection')).to_have_text('LIVE')
            expect(page.locator('#quick-model option')).to_have_count(2)
            page.locator('#quick-model').select_option('qwen2.5vl:7b')
            page.locator('#quick-model-save').click()
            expect(page.locator('#model')).to_contain_text('qwen2.5vl:7b')
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
            expect(page.locator('#events .event').first).to_be_visible()
            assert 'Acceptance fixture: driver unavailable' in page.locator('#notice').inner_text()
            page.locator('[data-tab=memory]').click()
            assert page.locator('#learnings').is_visible()
            page.locator('[data-tab=history]').click()
            page.locator('#sessions button').first.click()
            expect(page.locator('#replay .event').first).to_be_visible()
            page.locator('[data-tab=workspace]').click()
            page.screenshot(path=str(tmp_path/'cua-lab-ui.png'),full_page=True)
            page.set_viewport_size({'width':760,'height':1000})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            assert errors==[]
            browser.close()
    finally:
        server.should_exit=True;thread.join(10)
