import os,sys,uuid,tempfile
from pathlib import Path
os.environ['DATABASE_URL']='sqlite:///'+tempfile.mktemp(prefix='freedom-leads-',suffix='.sqlite')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from main import app

def account(client):
    email='test_'+uuid.uuid4().hex+'@example.com'
    r=client.post('/api/register',json={'email':email,'password':'securepassword2026'})
    assert r.status_code==201,r.text
    return email

def test_registration_lead_pipeline_and_logout():
    c=TestClient(app)
    email=account(c)
    assert c.get('/api/me').json()['email']==email
    missing=c.post('/api/leads',json={'name':'missing contact'})
    assert missing.status_code==422
    lead=c.post('/api/leads',json={'name':'Иван','phone':'+79991112233','message':'Квартира','source':'manual'})
    assert lead.status_code==201
    id=lead.json()['lead']['id']
    assert c.post('/api/leads',json={'name':'Иван','phone':'+79991112233'}).json()['created'] is False
    assert c.patch(f'/api/leads/{id}',json={'status':'won'}).status_code==200
    assert c.get('/api/stats').json()['conversion']==100.0
    assert 'Иван' in c.get('/api/export.csv').text
    assert c.post('/api/logout').status_code==200
    assert c.get('/api/me').status_code==401

def test_source_public_form_webhook_and_ownership():
    a=TestClient(app);b=TestClient(app);account(a);account(b)
    source=a.post('/api/sources',json={'name':'Telegram — недвижимость'}).json()
    slug=source['form'].split('/')[-1]
    assert b.get('/api/sources').json()==[]
    assert a.post('/api/public/'+slug,json={'name':'Без согласия','phone':'1234567'}).status_code==422
    good=a.post('/api/public/'+slug,json={'name':'Клиент','phone':'+79990002211','consent':True})
    assert good.status_code==201
    assert len(a.get('/api/leads').json())>=1
    assert b.get('/api/leads').json()==[]
    assert a.post('/api/webhook/'+slug,headers={'X-API-Key':'bad'},json={'phone':'+79991111111'}).status_code==401
    ok=a.post('/api/webhook/'+slug,headers={'X-API-Key':source['api_key_once']},json={'phone':'+79992223344'})
    assert ok.status_code==201
    first=a.get('/api/leads').json()[0]['id']
    assert b.patch('/api/leads/'+str(first),json={'status':'lost'}).status_code==404
    assert b.delete('/api/leads/'+str(first)).status_code==404

def test_task_scope():
    c=TestClient(app);account(c)
    assert c.post('/api/tasks',json={'title':'Позвонить','lead_id':999999999}).status_code==404
    task=c.post('/api/tasks',json={'title':'Позвонить','due':'2026-11-21T15:00'}).json()['id']
    assert c.patch('/api/tasks/'+str(task),json={'done':True}).status_code==200
    assert c.get('/api/tasks').json()[0]['done'] is True
