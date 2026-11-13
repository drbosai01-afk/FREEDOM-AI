/* Append to existing notebook service worker, do not replace its cache handlers.
   Browser-managed Background Sync requires an active cookie-bound verified account. */
const FREEDOM_OUTBOX_DB='freedom-realty-outbox';
async function freedomIDB(){
 return new Promise((resolve,reject)=>{
  const r=indexedDB.open(FREEDOM_OUTBOX_DB,1);
  r.onupgradeneeded=()=>{if(!r.result.objectStoreNames.contains('jobs'))r.result.createObjectStore('jobs');if(!r.result.objectStoreNames.contains('meta'))r.result.createObjectStore('meta')};
  r.onerror=()=>reject(r.error);r.onsuccess=()=>resolve(r.result);
 });
}
async function freedomDBOp(store,mode,act){
 const db=await freedomIDB();
 try{return await new Promise((resolve,reject)=>{const tx=db.transaction(store,mode);const req=act(tx.objectStore(store));let answer;req.onsuccess=()=>{answer=req.result};req.onerror=()=>reject(req.error);tx.oncomplete=()=>resolve(answer);tx.onerror=()=>reject(tx.error);tx.onabort=()=>reject(tx.error)})}
 finally{db.close()}
}
async function freedomNotify(type){
 const tabs=await self.clients.matchAll({type:'window',includeUncontrolled:true});
 for(const tab of tabs)tab.postMessage({type});
}
async function freedomSync(){
 const me=await fetch('/api/me',{cache:'no-store',credentials:'same-origin'});
 if(me.status===401||me.status===403){await freedomNotify('FREEDOM_SYNC_NEEDED');return}
 if(!me.ok)throw Error('Account unavailable');
 const user=await me.json();
 const allowed=await freedomDBOp('meta','readonly',s=>s.get('enabled:'+user.id));
 if(!allowed)return;
 const job=await freedomDBOp('jobs','readonly',s=>s.get('state:'+user.id));
 if(!job)return;
 const bytes=new TextEncoder().encode(JSON.stringify(job.data));
 const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),x=>x.toString(16).padStart(2,'0')).join('');
 async function post(path,method,body){
  const res=await fetch('/api/'+path,{method,cache:'no-store',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  if(res.status===409){await freedomNotify('FREEDOM_SYNC_CONFLICT');throw Error('conflict')}
  if(!res.ok)throw Error('Retry later: '+res.status);
  return res.json();
 }
 const upload=await post('backups','POST',{size:bytes.length,sha256:digest});
 for(let i=0;i<bytes.length;i+=upload.chunk_bytes){
  const part=bytes.subarray(i,i+upload.chunk_bytes);
  const hex=Array.from(part,x=>x.toString(16).padStart(2,'0')).join('');
  await post('backups/'+upload.id+'/chunks/'+Math.floor(i/upload.chunk_bytes),'PUT',{hex_data:hex});
 }
 await post('backups/'+upload.id+'/verify','POST',{});
 const result=await post('sync/from-backup','POST',{snapshot_id:upload.id,expected_version:job.expected_version});
 await freedomDBOp('meta','readwrite',s=>s.put(result.version,'base:'+job.uid));
 const pending=await freedomDBOp('jobs','readonly',s=>s.get('state:'+user.id));
 if(pending?.id===job.id)await freedomDBOp('jobs','readwrite',s=>s.delete('state:'+user.id));
 else if(pending?.uid===user.id && pending.expected_version===job.expected_version){
   pending.expected_version=result.version;
   await freedomDBOp('jobs','readwrite',s=>s.put(pending,'state:'+user.id));
 }
 await freedomNotify('FREEDOM_SYNC_DONE');
}
self.addEventListener('sync',event=>{if(event.tag==='freedom-realty-upload')event.waitUntil(freedomSync())});
