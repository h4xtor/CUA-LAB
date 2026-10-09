from fastapi.testclient import TestClient

def test_local_api_rejects_cross_origin_and_missing_token(tmp_path):
    from cua_lab.server import create_app
    with TestClient(create_app(tmp_path,token='test-auth')) as client:
        assert client.get('/api/health').status_code==200
        assert client.get('/api/status').status_code==401
        assert client.get('/api/status',headers={'X-Cua-Token':'test-auth'}).status_code==200
        assert client.post('/api/tasks',json={'objective':'test'},headers={'X-Cua-Token':'test-auth','Origin':'https://attacker.example'}).status_code==403
        assert client.get('/api/status',headers={'X-Cua-Token':'test-auth','Host':'attacker.example'}).status_code==403
        assert client.get('/').status_code==200

def test_private_images_require_authentication(tmp_path):
    from cua_lab.server import create_app
    with TestClient(create_app(tmp_path,token='test-auth')) as client:
        assert client.get('/api/images/health/test.png').status_code==401
        assert client.get('/api/images/health/test.png',headers={'X-Cua-Token':'test-auth'}).status_code==404


def test_loopback_origin_requires_exact_host_and_port(tmp_path):
    from cua_lab.server import create_app
    with TestClient(create_app(tmp_path,token='fixture')) as client:
        headers={'X-Cua-Token':'fixture','Host':'127.0.0.1:51234','Origin':'http://127.0.0.1:51234'}
        assert client.get('/api/status',headers=headers).status_code==200
        headers['Origin']='http://127.0.0.1:8768'
        assert client.get('/api/status',headers=headers).status_code==403


def test_auto_learning_sync_is_enabled_by_default_and_preference_survives_restart(tmp_path):
    from cua_lab.server import create_app
    headers={'X-Cua-Token':'fixture'}
    with TestClient(create_app(tmp_path,token='fixture')) as client:
        assert client.get('/api/status',headers=headers).json()['auto_sync']
        assert client.post('/api/memory/auto/off',headers=headers).json()=={'enabled':False}
    with TestClient(create_app(tmp_path,token='fixture')) as client:
        assert not client.get('/api/status',headers=headers).json()['auto_sync']


def test_session_recovery_returns_every_event_after_cursor(tmp_path):
    from cua_lab.server import create_app
    app=create_app(tmp_path,token='fixture')
    with TestClient(app) as client:
        store=app.state.store
        store.create('fixture','test',{})
        events=[store.event('fixture',i,'test',{'message':str(i)}) for i in range(300)]
        headers={'X-Cua-Token':'fixture'}
        assert client.get('/api/sessions/fixture',headers=headers).json()==events
        recovered=client.get('/api/sessions/fixture?after='+str(events[199]['id']),headers=headers).json()
        assert recovered==events[200:]
        assert client.get('/api/sessions/fixture?after=-1',headers=headers).status_code==422
