import uuid, re
from fastapi.testclient import TestClient
import main

def test_production_signup_verification_login_and_reset(monkeypatch):
    mail=[]
    monkeypatch.setattr(main,'ENV','production')
    monkeypatch.setattr(main,'PUBLIC','https://freedom.test')
    monkeypatch.setattr(main,'send_mail',lambda address,subject,body:mail.append((address,subject,body)))
    client=TestClient(main.app,base_url='https://freedom.test')
    email='prod_'+uuid.uuid4().hex+'@example.com'
    r=client.post('/api/register',json={'email':email,'password':'secure-password-2026'})
    assert r.status_code==201 and 'message' in r.json(),r.text
    assert client.post('/api/login',json={'email':email,'password':'secure-password-2026'}).status_code==403
    token=mail[-1][2].split('token=')[-1]
    assert client.get('/api/verify-email',params={'token':token}).status_code==200
    assert client.get('/api/verify-email',params={'token':token}).status_code==400
    logged=client.post('/api/login',json={'email':email,'password':'secure-password-2026'})
    assert logged.status_code==200,logged.text
    assert 'httponly' in logged.headers['set-cookie'].lower()
    assert 'secure' in logged.headers['set-cookie'].lower()
    assert client.get('/api/me').status_code==200
    assert client.post('/api/forgot-password',json={'email':email}).status_code==200
    reset_token=mail[-1][2].split(': ')[-1]
    assert client.post('/api/reset-password',json={'token':reset_token,'password':'different-pass-2026'}).status_code==200
    assert client.get('/api/me').status_code==401
    assert client.post('/api/login',json={'email':email,'password':'different-pass-2026'}).status_code==200
