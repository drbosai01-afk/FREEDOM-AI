import os, secrets, hashlib, hmac, json, time, csv, io, re, smtplib, ssl
from datetime import datetime,timezone,timedelta
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request, Response, Header, Depends, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse, HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import create_engine,Column,Integer,String,Text,ForeignKey,DateTime,Boolean,select,func,or_
from sqlalchemy.orm import declarative_base,sessionmaker
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
import jwt

ROOT=Path(__file__).parent
ENV=os.getenv('ENVIRONMENT','development');DB=os.getenv('DATABASE_URL','sqlite:///./leads.sqlite')
if DB.startswith('postgres://'): DB='postgresql+psycopg://'+DB[11:]
if DB.startswith('postgresql://'): DB='postgresql+psycopg://'+DB[13:]
KEY=os.getenv('JWT_SECRET') or (secrets.token_urlsafe(48) if ENV!='production' else '')
PUBLIC=os.getenv('PUBLIC_BASE_URL','http://127.0.0.1:8000').rstrip('/')
if ENV=='production' and (len(KEY)<48 or not DB.startswith('postgresql+psycopg://') or not PUBLIC.startswith('https://')):raise RuntimeError('Secure production config required: JWT_SECRET, Postgres, HTTPS PUBLIC_BASE_URL')
engine=create_engine(DB,connect_args={'check_same_thread':False} if DB.startswith('sqlite:') else {},pool_pre_ping=True)
Session=sessionmaker(bind=engine)
Base=declarative_base();ph=PasswordHasher();utc=lambda:datetime.now(timezone.utc)
class User(Base):
 __tablename__='users';id=Column(Integer,primary_key=True);email=Column(String(320),unique=True,nullable=False);password=Column(String(255),nullable=False);verified=Column(Boolean,nullable=False,default=True)
class EmailToken(Base):
 __tablename__='email_tokens';digest=Column(String(64),primary_key=True);owner=Column(Integer,ForeignKey('users.id'),nullable=False);purpose=Column(String(20),nullable=False);expires=Column(DateTime(timezone=True),nullable=False)
class SessionKey(Base):
 __tablename__='sessions';hash=Column(String(64),primary_key=True);owner=Column(Integer,ForeignKey('users.id'),nullable=False)
class Lead(Base):
 __tablename__='leads';id=Column(Integer,primary_key=True);owner=Column(Integer,ForeignKey('users.id'),index=True,nullable=False);name=Column(String(160),default='');phone=Column(String(60),default='');email=Column(String(320),default='');message=Column(Text,default='');city=Column(String(100),default='');budget=Column(String(100),default='');status=Column(String(30),default='new');source=Column(String(150),default='manual');utm_source=Column(String(150),default='');utm_medium=Column(String(150),default='');utm_campaign=Column(String(150),default='');tags=Column(String(500),default='');consent=Column(Boolean,default=False);score=Column(Integer,default=0);created=Column(DateTime(timezone=True),default=utc)
class Source(Base):
 __tablename__='sources';id=Column(Integer,primary_key=True);owner=Column(Integer,ForeignKey('users.id'),index=True);name=Column(String(120));slug=Column(String(50),unique=True);secret_hash=Column(String(64));active=Column(Boolean,default=True);created=Column(DateTime(timezone=True),default=utc)
class Task(Base):
 __tablename__='tasks';id=Column(Integer,primary_key=True);owner=Column(Integer,ForeignKey('users.id'),index=True);title=Column(String(255));done=Column(Boolean,default=False);lead_id=Column(Integer,nullable=True);due=Column(String(40),default='')
class Note(Base):
 __tablename__='lead_notes';id=Column(Integer,primary_key=True);owner=Column(Integer,ForeignKey('users.id'),nullable=False,index=True);lead_id=Column(Integer,ForeignKey('leads.id'),nullable=False,index=True);body=Column(Text,nullable=False);created=Column(DateTime(timezone=True),default=utc)
class Activity(Base):
 __tablename__='activities';id=Column(Integer,primary_key=True);owner=Column(Integer,ForeignKey('users.id'),nullable=False,index=True);lead_id=Column(Integer,nullable=True);event=Column(String(80),nullable=False);details=Column(String(500),default='');created=Column(DateTime(timezone=True),default=utc)
class Attempt(Base):
 __tablename__='attempts';id=Column(Integer,primary_key=True);actor=Column(String(64),index=True);created=Column(Integer,index=True)
app=FastAPI(title='FREEDOM LEADS API',version='1.0')
Base.metadata.create_all(engine)
def session():
 with Session() as db:yield db
class Credentials(BaseModel):email:str=Field(min_length=6,max_length=320);password:str=Field(min_length=10,max_length=128)
class LeadData(BaseModel):name:str=Field(default='',max_length=160);phone:str=Field(default='',max_length=60);email:str=Field(default='',max_length=320);message:str=Field(default='',max_length=3000);city:str=Field(default='',max_length=100);budget:str=Field(default='',max_length=100);source:str=Field(default='manual',max_length=150);utm_source:str=Field(default='',max_length=150);utm_medium:str=Field(default='',max_length=150);utm_campaign:str=Field(default='',max_length=150);tags:str=Field(default='',max_length=500);honeypot:str=Field(default='',max_length=150);consent:bool=False
class Patch(BaseModel):
 status:str|None=None
 name:str|None=Field(default=None,max_length=160)
 phone:str|None=Field(default=None,max_length=60)
 email:str|None=Field(default=None,max_length=320)
 message:str|None=Field(default=None,max_length=3000)
 city:str|None=Field(default=None,max_length=100)
 budget:str|None=Field(default=None,max_length=100)
 tags:str|None=Field(default=None,max_length=500)
class NoteData(BaseModel):body:str=Field(min_length=1,max_length=3000)
class SourcePatch(BaseModel):active:bool

class SourceData(BaseModel):name:str=Field(min_length=2,max_length=120)
class TaskData(BaseModel):title:str=Field(min_length=1,max_length=255);lead_id:int|None=None;due:str=Field(default='',max_length=40)
class TaskPatch(BaseModel):done:bool

def ratelimit(db,request,email):
 actor=hashlib.sha256(((request.client.host if request.client else 'unknown')+':'+email).encode()).hexdigest();cutoff=int(time.time())-3600
 if db.scalar(select(func.count()).select_from(Attempt).where(Attempt.actor==actor,Attempt.created>=cutoff))>=12:raise HTTPException(429,'Слишком много попыток, повторите через час')
 db.add(Attempt(actor=actor,created=int(time.time())));db.commit()
def send_mail(address,subject,body):
 host=os.getenv('SMTP_HOST','');user=os.getenv('SMTP_USER','');password=os.getenv('SMTP_PASSWORD','');sender=os.getenv('SMTP_FROM','')
 if not all((host,user,password,sender)):raise RuntimeError('SMTP not configured')
 msg=__import__('email.message',fromlist=['EmailMessage']).EmailMessage()
 msg['Subject']=subject;msg['From']=sender;msg['To']=address;msg.set_content(body)
 with smtplib.SMTP(host,int(os.getenv('SMTP_PORT','587')),timeout=12) as smtp:
  smtp.starttls(context=ssl.create_default_context());smtp.login(user,password);smtp.send_message(msg)
def email_token(db,user,purpose):
 value=secrets.token_urlsafe(48)
 row=EmailToken(digest=hashlib.sha256(value.encode()).hexdigest(),owner=user.id,purpose=purpose,expires=utc()+timedelta(hours=1 if purpose=='reset' else 24))
 db.add(row);db.commit();return value
def take_token(db,value,purpose):
 if len(value)<40 or len(value)>256:raise HTTPException(400,'Неверная ссылка')
 row=db.get(EmailToken,hashlib.sha256(value.encode()).hexdigest())
 if not row or row.purpose!=purpose or row.expires.replace(tzinfo=timezone.utc)<utc():raise HTTPException(400,'Срок ссылки истёк')
 u=db.get(User,row.owner);db.delete(row);db.commit()
 if not u:raise HTTPException(400,'Аккаунт не найден')
 return u
def signed(user,response,db):
 token=jwt.encode({'sub':str(user.id),'exp':int(time.time())+43200,'jti':secrets.token_urlsafe(24)},KEY,algorithm='HS256');db.add(SessionKey(hash=hashlib.sha256(token.encode()).hexdigest(),owner=user.id));db.commit();response.set_cookie('freedom_session',token,httponly=True,secure=ENV=='production',samesite='strict',max_age=43200,path='/');return {'email':user.email}
def current(request:Request,db=Depends(session)):
 token=request.cookies.get('freedom_session');
 if not token:raise HTTPException(401,'Войдите в аккаунт')
 try:uid=int(jwt.decode(token,KEY,algorithms=['HS256'])['sub'])
 except (jwt.PyJWTError,ValueError,KeyError):raise HTTPException(401,'Сеанс истёк')
 s=db.get(SessionKey,hashlib.sha256(token.encode()).hexdigest());u=db.get(User,uid)
 if not s or not u or s.owner!=uid or not u.verified:raise HTTPException(401,'Сеанс закрыт')
 if request.method not in ('GET','HEAD','OPTIONS'):
  origin=request.headers.get('origin');
  if origin and origin!=PUBLIC:raise HTTPException(403,'Запрос с чужого домена')
  if ENV=='production' and not origin:raise HTTPException(403,'Не указан Origin')
 return u
@app.post('/api/register',status_code=201)
def register(c:Credentials,response:Response,request:Request,db=Depends(session)):
 email=c.email.lower().strip();ratelimit(db,request,email)
 if '@' not in email or '.' not in email.split('@')[-1]:raise HTTPException(422,'Неверная почта')
 if db.scalar(select(User).where(User.email==email)):raise HTTPException(409,'Аккаунт уже есть')
 u=User(email=email,password=ph.hash(c.password),verified=ENV!='production');db.add(u);db.commit();db.refresh(u)
 if ENV=='production':
  token=email_token(db,u,'verify')
  try:send_mail(email,'Подтверждение FREEDOM LEADS',f'Подтвердите email в течение 24 часов: {PUBLIC}/api/verify-email?token={token}')
  except Exception:raise HTTPException(503,'Не удалось отправить письмо. Попробуйте повторить подтверждение позже.')
  return {'message':'Проверьте почту и подтвердите email'}
 return signed(u,response,db)
@app.post('/api/login')
def login(c:Credentials,response:Response,request:Request,db=Depends(session)):
 email=c.email.lower().strip();ratelimit(db,request,email);u=db.scalar(select(User).where(User.email==email))
 try:valid=u and ph.verify(u.password,c.password)
 except VerifyMismatchError:valid=False
 if not valid:raise HTTPException(401,'Неверная почта или пароль')
 if not u.verified:raise HTTPException(403,'Подтвердите email по ссылке из письма')
 return signed(u,response,db)
@app.get('/api/verify-email',response_class=HTMLResponse)
def verify_email(token:str,db=Depends(session)):
 u=take_token(db,token,'verify');u.verified=True;db.commit()
 return HTMLResponse('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Адрес подтверждён</title><body style="font:18px system-ui;background:#090f1c;color:white;padding:12vh 20px;text-align:center"><h1>Email подтверждён</h1><p>Вернитесь в FREEDOM LEADS и войдите в аккаунт.</p><a style="color:#b0bfff" href="/">Перейти ко входу</a></body>')
class EmailRequest(BaseModel):email:str=Field(min_length=6,max_length=320)
class PasswordReset(BaseModel):token:str=Field(min_length=40,max_length=256);password:str=Field(min_length=10,max_length=128)
@app.post('/api/resend-verification')
def resend_verification(d:EmailRequest,request:Request,db=Depends(session)):
 email=d.email.lower().strip();ratelimit(db,request,'resend:'+email);u=db.scalar(select(User).where(User.email==email))
 if u and not u.verified and ENV=='production':
  token=email_token(db,u,'verify')
  try:send_mail(email,'Подтверждение FREEDOM LEADS',f'{PUBLIC}/api/verify-email?token={token}')
  except Exception:raise HTTPException(503,'Почтовый сервис недоступен')
 return {'message':'Если адрес ожидает подтверждения, письмо отправлено'}
@app.post('/api/forgot-password')
def forgot_password(d:EmailRequest,request:Request,db=Depends(session)):
 email=d.email.lower().strip();ratelimit(db,request,'reset:'+email);u=db.scalar(select(User).where(User.email==email))
 if u and ENV=='production':
  token=email_token(db,u,'reset')
  try:send_mail(email,'Сброс пароля FREEDOM LEADS',f'Откройте приложение и используйте одноразовый код сброса (1 час): {token}')
  except Exception:raise HTTPException(503,'Почтовый сервис недоступен')
 return {'message':'Если аккаунт существует, инструкция отправлена'}
@app.post('/api/reset-password')
def reset_password(d:PasswordReset,db=Depends(session)):
 u=take_token(db,d.token,'reset');u.password=ph.hash(d.password)
 db.query(SessionKey).filter(SessionKey.owner==u.id).delete();db.commit()
 return {'ok':True}
@app.post('/api/logout')
def logout(request:Request,response:Response,db=Depends(session)):
 token=request.cookies.get('freedom_session');s=db.get(SessionKey,hashlib.sha256(token.encode()).hexdigest()) if token else None
 if s:db.delete(s);db.commit()
 response.delete_cookie('freedom_session',path='/');return {'ok':True}
@app.get('/api/me')
def me(u=Depends(current)):return {'id':u.id,'email':u.email}
def aslead(l):return {k:getattr(l,k) for k in ('id','name','phone','email','message','city','budget','status','source','utm_source','utm_medium','utm_campaign','tags','consent','score')}|{'created':l.created.isoformat()}
def audit(db,owner,event,lead_id=None,details=''):
 db.add(Activity(owner=owner,event=event,lead_id=lead_id,details=str(details)[:500]))
def store(db,owner,d,source=None):
 src=source or d.source
 existing=db.scalar(select(Lead).where(Lead.owner==owner,Lead.source==src,Lead.phone==d.phone)) if d.phone else None
 if existing:return existing,False
 score=min(100,(20 if d.phone else 0)+(20 if d.email else 0)+(30 if d.budget else 0)+(20 if len(d.message)>20 else 0)+(10 if d.consent else 0));row=Lead(owner=owner,source=src,score=score,**d.model_dump(exclude={'source','honeypot'}));db.add(row);db.flush();audit(db,owner,'lead.created',row.id,src);db.commit();db.refresh(row);return row,True
@app.get('/api/leads')
def get_leads(u=Depends(current),db=Depends(session)):return [aslead(l) for l in db.scalars(select(Lead).where(Lead.owner==u.id).order_by(Lead.id.desc()).limit(500))]
@app.post('/api/leads',status_code=201)
def add(d:LeadData,u=Depends(current),db=Depends(session)):
 if not (d.phone or d.email):raise HTTPException(422,'Нужен контакт')
 row,created=store(db,u.id,d);return {'lead':aslead(row),'created':created}
@app.patch('/api/leads/{id}')
def patch(id:int,d:Patch,u=Depends(current),db=Depends(session)):
 row=db.scalar(select(Lead).where(Lead.id==id,Lead.owner==u.id))
 if not row:raise HTTPException(404,'Не найдено')
 if d.status is not None and d.status not in ('new','working','qualified','meeting','won','lost'):
  raise HTTPException(422,'Неизвестный статус')
 changes=[]
 for field,value in d.model_dump(exclude_none=True).items():
  if getattr(row,field)!=value:
   setattr(row,field,value);changes.append(field)
 if changes:audit(db,u.id,'lead.updated',row.id,','.join(changes))
 db.commit();return {'ok':True}
@app.delete('/api/leads/{id}')
def delete(id:int,u=Depends(current),db=Depends(session)):
 row=db.scalar(select(Lead).where(Lead.id==id,Lead.owner==u.id))
 if not row:raise HTTPException(404,'Не найдено')
 audit(db,u.id,'lead.deleted',row.id,row.name);db.delete(row);db.commit();return {'ok':True}
@app.get('/api/stats')
def stats(u=Depends(current),db=Depends(session)):
 statuses=dict(db.execute(select(Lead.status,func.count()).where(Lead.owner==u.id).group_by(Lead.status)).all());sources=dict(db.execute(select(Lead.source,func.count()).where(Lead.owner==u.id).group_by(Lead.source)).all());total=sum(statuses.values());return {'total':total,'statuses':statuses,'sources':sources,'conversion':round(100*statuses.get('won',0)/total,1) if total else 0}
@app.get('/api/export.csv')
def export(u=Depends(current),db=Depends(session)):
 buf=io.StringIO();w=csv.writer(buf);cols=['id','name','phone','email','city','budget','status','source','message'];w.writerow(cols)
 for l in db.scalars(select(Lead).where(Lead.owner==u.id)):
  w.writerow([("'"+str(v) if str(v).startswith(('=','+','-','@')) else v) for v in [getattr(l,x) for x in cols]])
 return StreamingResponse(iter(['\ufeff'+buf.getvalue()]),media_type='text/csv',headers={'Content-Disposition':'attachment;filename="leads.csv"'})
@app.get('/api/sources')
def sources(u=Depends(current),db=Depends(session)):
 return [{'id':s.id,'name':s.name,'active':s.active,'form':PUBLIC+'/f/'+s.slug,'webhook':PUBLIC+'/api/webhook/'+s.slug} for s in db.scalars(select(Source).where(Source.owner==u.id))]
@app.post('/api/sources',status_code=201)
def new_source(d:SourceData,u=Depends(current),db=Depends(session)):
 slug=secrets.token_urlsafe(9).replace('-','x').replace('_','y');secret='fl_'+secrets.token_urlsafe(27);s=Source(owner=u.id,name=d.name,slug=slug,secret_hash=hashlib.sha256(secret.encode()).hexdigest());db.add(s);db.commit();return {'name':s.name,'form':PUBLIC+'/f/'+slug,'webhook':PUBLIC+'/api/webhook/'+slug,'api_key_once':secret}
def alert_telegram(name:str,contact:str,source:str,message:str):
 token=os.getenv('TELEGRAM_BOT_TOKEN','');chat=os.getenv('TELEGRAM_CHAT_ID','')
 if not token or not chat:return
 try:
  import httpx
  msg=f'FREEDOM LEADS · новая заявка\n{source[:100]}\n{name[:100]} · {contact[:100]}\n{message[:500]}'
  httpx.post('https://api.telegram.org/bot'+token+'/sendMessage',json={'chat_id':chat,'text':msg},timeout=5)
 except Exception:pass
@app.post('/api/public/{slug}',status_code=201)
def public_lead(slug:str,d:LeadData,background_tasks:BackgroundTasks,request:Request,db=Depends(session)):
 s=db.scalar(select(Source).where(Source.slug==slug))
 if not s or not s.active:raise HTTPException(404,'Форма не найдена')
 if d.honeypot:return {'ok':True,'created':False}
 if ENV=='production' and not os.getenv('PRIVACY_POLICY_URL','').startswith('https://'):
  raise HTTPException(503,'Форма временно недоступна до публикации политики обработки данных')
 ratelimit(db,request,'public:'+slug)
 if not d.consent or not (d.phone or d.email):raise HTTPException(422,'Требуется контакт и согласие')
 row,created=store(db,s.owner,d,s.name)
 if created:background_tasks.add_task(alert_telegram,d.name,d.phone or d.email,s.name,d.message)
 return {'ok':True,'created':created}
@app.post('/api/webhook/{slug}',status_code=201)
def webhook(slug:str,d:LeadData,background_tasks:BackgroundTasks,x_api_key:str=Header(default=''),db=Depends(session)):
 s=db.scalar(select(Source).where(Source.slug==slug))
 if not s or not s.active or not x_api_key or not hmac.compare_digest(hashlib.sha256(x_api_key.encode()).hexdigest(),s.secret_hash):raise HTTPException(401,'Неверный ключ')
 if not (d.phone or d.email):raise HTTPException(422,'Нужен контакт')
 row,created=store(db,s.owner,d,s.name)
 if created:background_tasks.add_task(alert_telegram,d.name,d.phone or d.email,s.name,d.message)
 return {'id':row.id,'created':created}
@app.get('/api/tasks')
def tasks(u=Depends(current),db=Depends(session)):return [{k:getattr(t,k) for k in ('id','title','done','lead_id','due')} for t in db.scalars(select(Task).where(Task.owner==u.id).order_by(Task.id.desc()))]
@app.post('/api/tasks',status_code=201)
def task_create(t:TaskData,u=Depends(current),db=Depends(session)):
 if t.lead_id and not db.scalar(select(Lead).where(Lead.id==t.lead_id,Lead.owner==u.id)):raise HTTPException(404,'Чужая заявка')
 row=Task(owner=u.id,**t.model_dump());db.add(row);db.commit();audit(db,u.id,'task.created',t.lead_id,t.title);db.commit();return {'id':row.id}
@app.patch('/api/tasks/{id}')
def task_patch(id:int,d:TaskPatch,u=Depends(current),db=Depends(session)):
 t=db.scalar(select(Task).where(Task.id==id,Task.owner==u.id))
 if not t:raise HTTPException(404,'Нет задачи')
 t.done=d.done;db.commit();return {'ok':True}
@app.get('/api/leads/{lead_id}/notes')
def get_notes(lead_id:int,u=Depends(current),db=Depends(session)):
 if not db.scalar(select(Lead.id).where(Lead.id==lead_id,Lead.owner==u.id)):raise HTTPException(404,'Заявка не найдена')
 return [{'id':n.id,'body':n.body,'created':n.created.isoformat()} for n in db.scalars(select(Note).where(Note.owner==u.id,Note.lead_id==lead_id).order_by(Note.id.desc()).limit(100))]
@app.post('/api/leads/{lead_id}/notes',status_code=201)
def add_note(lead_id:int,d:NoteData,u=Depends(current),db=Depends(session)):
 if not db.scalar(select(Lead.id).where(Lead.id==lead_id,Lead.owner==u.id)):raise HTTPException(404,'Заявка не найдена')
 n=Note(owner=u.id,lead_id=lead_id,body=d.body.strip());db.add(n);audit(db,u.id,'note.created',lead_id);db.commit();db.refresh(n)
 return {'id':n.id,'body':n.body}
@app.get('/api/activity')
def activity(u=Depends(current),db=Depends(session)):
 return [{'id':a.id,'lead_id':a.lead_id,'event':a.event,'details':a.details,'created':a.created.isoformat()} for a in db.scalars(select(Activity).where(Activity.owner==u.id).order_by(Activity.id.desc()).limit(150))]
@app.patch('/api/sources/{source_id}')
def change_source(source_id:int,d:SourcePatch,u=Depends(current),db=Depends(session)):
 src=db.scalar(select(Source).where(Source.id==source_id,Source.owner==u.id))
 if not src:raise HTTPException(404,'Источник не найден')
 src.active=d.active;audit(db,u.id,'source.updated',None,src.name);db.commit();return {'ok':True,'active':src.active}
@app.get('/api/leads.csv')
def leads_csv_alias(u=Depends(current),db=Depends(session)):
 return export(u,db)
@app.get('/api/overview')
def overview(u=Depends(current),db=Depends(session)):
 count=db.scalar(select(func.count(Lead.id)).where(Lead.owner==u.id))
 uncompleted=db.scalar(select(func.count(Task.id)).where(Task.owner==u.id,Task.done==False))
 return {'leads':count,'pending_tasks':uncompleted,'active_sources':db.scalar(select(func.count(Source.id)).where(Source.owner==u.id,Source.active==True))}
@app.get('/api/health')
def health(db=Depends(session)):
 smtp_ok=all(os.getenv(k) for k in ('SMTP_HOST','SMTP_USER','SMTP_PASSWORD','SMTP_FROM'))
 db_ok=bool(db.scalar(select(func.count()).select_from(User))>=0)
 ready=db_ok and (ENV!='production' or (smtp_ok and DB.startswith('postgresql+psycopg://') and PUBLIC.startswith('https://')))
 from fastapi.responses import JSONResponse
 return JSONResponse({'ready':ready,'environment':ENV,'database':db_ok,'email_configured':smtp_ok},status_code=200 if ready else 503)
@app.get('/f/{slug}')
def form(slug:str,db=Depends(session)):
 if not db.scalar(select(Source).where(Source.slug==slug,Source.active==True)):raise HTTPException(404,'Форма не найдена')
 return FileResponse(ROOT/'form.html')
@app.get('/api/public-config')
def public_config():
 return {'privacy_policy_url':os.getenv('PRIVACY_POLICY_URL','')}
@app.get('/manifest.webmanifest')
def manifest():
 from fastapi.responses import JSONResponse
 return JSONResponse({'name':'FREEDOM LEADS','short_name':'LEADS','start_url':'/','display':'standalone','background_color':'#090f1c','theme_color':'#6378ff','lang':'ru','icons':[{'src':'/static/icon-192.png','sizes':'192x192','type':'image/png'},{'src':'/static/icon-512.png','sizes':'512x512','type':'image/png'}]})
@app.get('/static/{name}')
def static_asset(name:str):
 if name not in ('sw.js','icon-192.png','icon-512.png'):raise HTTPException(404,'Not found')
 return FileResponse(ROOT/'static'/name)
@app.get('/sw.js')
def service_worker():return FileResponse(ROOT/'static'/'sw.js',media_type='application/javascript',headers={'Service-Worker-Allowed':'/'})
@app.get('/')
def home():return FileResponse(ROOT/'index.html')
