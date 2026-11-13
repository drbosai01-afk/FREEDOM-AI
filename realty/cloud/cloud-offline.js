/* FREEDOM REALTY: opt-in offline-first outbox. No silent restores or merges.
   Load AFTER cloud-sync-addon.js and BEFORE app.js; append sw-cloud-extension.js to existing sw.js.
   The original notebook keeps writing to IndexedDB even without network. */
(() => {
'use strict';
const NAME='freedom-realty-outbox', TAG='freedom-realty-upload';
let enabled=false, uid=null, busy=false;
const el=id=>document.getElementById(id);
function openOutbox(){
 return new Promise((res,rej)=>{
  const r=indexedDB.open(NAME,1);
  r.onupgradeneeded=()=>{
   if(!r.result.objectStoreNames.contains('jobs'))r.result.createObjectStore('jobs');
   if(!r.result.objectStoreNames.contains('meta'))r.result.createObjectStore('meta');
  };
  r.onsuccess=()=>res(r.result);r.onerror=()=>rej(r.error);
 });
}
async function operation(store,mode,command){
 const db=await openOutbox();
 try{return await new Promise((resolve,reject)=>{
  const tx=db.transaction(store,mode),req=command(tx.objectStore(store));
  let answer;
  req.onsuccess=()=>{answer=req.result};req.onerror=()=>reject(req.error);
  tx.oncomplete=()=>resolve(answer);
  tx.onerror=()=>reject(tx.error);tx.onabort=()=>reject(tx.error);
 })}finally{db.close()}
}
async function get(store,key){return operation(store,'readonly',s=>s.get(key))}
async function put(store,key,value){return operation(store,'readwrite',s=>s.put(value,key))}
async function drop(store,key){return operation(store,'readwrite',s=>s.delete(key))}
const info=s=>{const v=el('fr-outbox-status');if(v)v.textContent=s};
async function registerSync(){
 if(!('serviceWorker' in navigator))return;
 try{
  const reg=await navigator.serviceWorker.ready;
  if(reg.sync && reg.sync.register)await reg.sync.register(TAG);
  else if(navigator.onLine)await syncForeground();
 }catch(e){info('Синхронизация будет повторена при открытии приложения: '+e.message)}
}
async function readLocal(){
 return new Promise((resolve,reject)=>{
  const r=indexedDB.open('krasnodar-notebook');
  r.onerror=()=>reject(r.error);
  r.onsuccess=()=>{
   const db=r.result;
   if(!db.objectStoreNames.contains('store')){db.close();reject(Error('Нет локального каталога'));return}
   const get=db.transaction('store','readonly').objectStore('store').get('state');
   get.onsuccess=()=>{db.close();resolve(get.result)};
   get.onerror=()=>{db.close();reject(get.error)};
  };
 });
}
async function queueCurrent(){
 if(!enabled||uid===null)return;
 try{
  const state=await readLocal();
  if(!state || !Array.isArray(state.properties)||!Array.isArray(state.queue))return;
  const saved=await get('meta','base:'+uid);
  // Without a verified shared base, a local change must never replace existing cloud state.
  const base=saved===undefined?0:Number(saved);
  const job={id:String(Date.now())+'-'+Math.random().toString(36).slice(2),
    uid,created:Date.now(),expected_version:base,data:state};
  await put('jobs','state:'+uid,job);
  info(navigator.onLine?'Изменение ожидает синхронизации':'Офлайн: изменение сохранено на устройстве');
  await registerSync();
 }catch(e){info('Ошибка локальной очереди: '+e.message)}
}
async function syncForeground(){
 if(busy||!navigator.onLine||!enabled)return;
 busy=true;
 try{
  const job=await get('jobs','state:'+uid);if(!job)return;
  const auth=await fetch('/api/me',{credentials:'same-origin',cache:'no-store'});
  if(!auth.ok)throw Error('Сеанс истёк. Сначала войдите.');
  const person=await auth.json();
  if(person.id!==job.uid)throw Error('Данные ожидают входа в исходный аккаунт');
  const bytes=new TextEncoder().encode(JSON.stringify(job.data));
  const checksum=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),b=>b.toString(16).padStart(2,'0')).join('');
  async function request(path,method,body){
   const r=await fetch('/api/'+path,{method,credentials:'same-origin',cache:'no-store',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
   if(!r.ok){if(r.status===409)throw Error('Конфликт версий — сохранено на устройстве');throw Error('HTTP '+r.status)}
   return r.json();
  }
  const upload=await request('backups','POST',{size:bytes.length,sha256:checksum});
  for(let i=0;i<bytes.length;i+=upload.chunk_bytes){
   const part=bytes.subarray(i,i+upload.chunk_bytes);
   const hex=Array.from(part,b=>b.toString(16).padStart(2,'0')).join('');
   await request('backups/'+upload.id+'/chunks/'+Math.floor(i/upload.chunk_bytes),'PUT',{hex_data:hex});
  }
  await request('backups/'+upload.id+'/verify','POST',{});
  const saved=await request('sync/from-backup','POST',{snapshot_id:upload.id,expected_version:job.expected_version});
  await put('meta','base:'+job.uid,saved.version);
  const latest=await get('jobs','state:'+uid);
  if(latest?.id===job.id)await drop('jobs','state:'+uid);
  else if(latest?.uid===uid && latest.expected_version===job.expected_version){
   latest.expected_version=saved.version;
   await put('jobs','state:'+uid,latest);
   await registerSync();
  }
  info('Синхронизировано: версия '+saved.version);
 }catch(e){info('Синхронизация отложена: '+e.message)}
 finally{busy=false}
}
// Observe committed writes from existing notebook without altering its state.
const original=IDBObjectStore.prototype.put;
IDBObjectStore.prototype.put=function(value,key){
 const relevant=enabled&&this.name==='store'&&key==='state'&&this.transaction.db.name==='krasnodar-notebook';
 const request=original.apply(this,arguments);
 if(relevant)this.transaction.addEventListener('complete',()=>{queueCurrent()}, {once:true});
 return request;
};
const panel=document.getElementById('freedom-cloud');
if(panel){
 const div=document.createElement('div');
 div.innerHTML='<p><label><input type="checkbox" id="fr-auto-sync"> Автосинхронизация при наличии интернета</label></p><small id="fr-outbox-status">Выключена — данные остаются локально</small>';
 panel.appendChild(div);
 el('fr-auto-sync').addEventListener('change',async e=>{
  if(!e.target.checked){const old=uid;enabled=false;uid=null;if(old!==null)await put('meta','enabled:'+old,false);info('Автосинхронизация выключена');return}
  try{
   const r=await fetch('/api/me',{credentials:'same-origin',cache:'no-store'});
   if(!r.ok)throw Error('Для фоновой синхронизации нужно войти и подтвердить email');
   const me=await r.json();
   uid=me.id;enabled=true;
   const current=await fetch('/api/sync/state',{credentials:'same-origin',cache:'no-store'});
   if(!current.ok)throw Error('Не удалось сверить облачную версию');
   const cloud=await current.json();
   const base=await get('meta','base:'+uid);
   if(base===undefined && cloud.version>0){
    const state=await readLocal();
    if(JSON.stringify(state)!==JSON.stringify(cloud.data)){
     enabled=false;uid=null;
     throw Error('На сервере уже есть отличающаяся база. Сначала сравните её вручную.');
    }
    await put('meta','base:'+uid,cloud.version);
   }
   if(base!==undefined && Number(base)!==cloud.version){
    enabled=false;uid=null;
    throw Error('Облачная версия изменилась. Сначала сравните базы вручную.');
   }
   await put('meta','enabled:'+uid,true);
   info('Включено для аккаунта '+me.email);
   await queueCurrent();
  }catch(err){enabled=false;uid=null;e.target.checked=false;info(err.message)}
 });
}
window.addEventListener('online',()=>{if(enabled){registerSync();syncForeground()}});
document.addEventListener('visibilitychange',()=>{if(enabled&&!document.hidden){queueCurrent();syncForeground()}});
if('serviceWorker' in navigator)navigator.serviceWorker.addEventListener('message',e=>{
 if(e.data?.type==='FREEDOM_SYNC_NEEDED'&&enabled)syncForeground();
 if(e.data?.type==='FREEDOM_SYNC_CONFLICT')info('Конфликт облачной версии — требуется ручная сверка');
 if(e.data?.type==='FREEDOM_SYNC_DONE')info('Фоновая синхронизация завершена');
});
})();