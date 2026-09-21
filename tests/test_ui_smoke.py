"""Optional browser test: run explicitly with CUA_UI_TEST=1 and Playwright installed."""
import os
import threading
import time
import pytest

@pytest.mark.skipif(os.getenv('CUA_UI_TEST')!='1',reason='Optional local browser test')
def test_real_browser_layout_health_and_failed_task(tmp_path):
    import uvicorn
    from playwright.sync_api import sync_playwright, expect
    from cua_lab.server import create_app
    app=create_app(tmp_path,token='browser-test-token')
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
            page.locator('#prompt').fill('Inspect desktop read-only')
            page.locator('#start').click()
            expect(page.locator('#state')).to_have_text('FAILED')
            assert 'Windows interactive desktop required' in page.locator('#notice').inner_text()
            page.locator('[data-tab=memory]').click()
            assert page.locator('#learnings').is_visible()
            page.locator('[data-tab=history]').click()
            page.locator('#sessions button').first.click()
            assert page.locator('#replay .event').count()>0
            page.locator('[data-tab=workspace]').click()
            page.screenshot(path='/tmp/cua-lab-ui.png',full_page=True)
            page.set_viewport_size({'width':760,'height':1000})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            assert errors==[]
            browser.close()
    finally:
        server.should_exit=True;thread.join(10)
