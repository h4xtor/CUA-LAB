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
