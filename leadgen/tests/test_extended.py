import uuid
from fastapi.testclient import TestClient
from main import app

def register(client):
    email='test_ext_'+uuid.uuid4().hex+'@example.com'
    response=client.post('/api/register',json={'email':email,'password':'strong_pass_987654'})
    assert response.status_code==201,response.text
    return email

def test_notes_activity_tags_and_tenant_isolation():
    a,b=TestClient(app),TestClient(app)
    register(a);register(b)
    made=a.post('/api/leads',json={'name':'Мария','phone':'+70000001231','utm_source':'vk','utm_campaign':'autumn','tags':'горячий'})
    assert made.status_code==201,made.text
    lid=made.json()['lead']['id']
    assert a.patch(f'/api/leads/{lid}',json={'status':'working','tags':'срочно, ипотека','budget':'5 млн'}).status_code==200
    lead=next(x for x in a.get('/api/leads').json() if x['id']==lid)
    assert lead['utm_source']=='vk' and lead['tags']=='срочно, ипотека'
    assert a.post(f'/api/leads/{lid}/notes',json={'body':'Позвонить завтра'}).status_code==201
    assert a.get(f'/api/leads/{lid}/notes').json()[0]['body']=='Позвонить завтра'
    assert a.get('/api/activity').json()[0]['event']=='note.created'
    assert b.get(f'/api/leads/{lid}/notes').status_code==404
    assert b.post(f'/api/leads/{lid}/notes',json={'body':'Чужой аккаунт'}).status_code==404
    assert b.get('/api/activity').json()==[]
    assert a.get('/api/overview').json()['leads']>=1

def test_source_disabling_and_campaign_capture():
    a=TestClient(app);register(a)
    source=a.post('/api/sources',json={'name':'Форма рекламы'}).json()
    src=next(x for x in a.get('/api/sources').json() if x['name']=='Форма рекламы')
    slug=source['form'].split('/')[-1]
    spam=a.post('/api/public/'+slug,json={'phone':'+79990009999','consent':True,'honeypot':'robot'})
    assert spam.status_code==201 and not spam.json()['created']
    legit=a.post('/api/public/'+slug,json={'phone':'+79998887766','consent':True,'utm_source':'yandex','utm_medium':'cpc','utm_campaign':'q4'})
    assert legit.status_code==201 and legit.json()['created']
    assert any(l['utm_campaign']=='q4' for l in a.get('/api/leads').json())
    assert a.patch('/api/sources/'+str(src['id']),json={'active':False}).status_code==200
    assert a.get('/f/'+slug).status_code==404
    assert a.post('/api/public/'+slug,json={'phone':'+79991111111','consent':True}).status_code==404
    assert a.post('/api/webhook/'+slug,json={'phone':'+79991111111'},headers={'X-API-Key':source['api_key_once']}).status_code==401
