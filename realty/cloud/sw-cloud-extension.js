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
 try{return await new Promise((resolve,reject)=>{const tx=db.transaction(store,mode);const req=act(tx.objectStore(store));req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error);tx.onabort=()=>reject(tx.error)})}
 finally{db.close()}
}
async function freedomNotify(type){
 const tabs=await self.clients.matchAll({type:'window',includeUncontrolled:true});
 for(const tab of tabs)tab.postMessage({type});
}
async function freedomSync(){
 const job=await freedomDBOp('jobs','readonly',s=>s.get('state'));
 if(!job)return;
 const me=await fetch('/api/me',{cache:'no-store',credentials:'same-origin'});
 if(me.status===401||me.status===403){await freedomNotify('FREEDOM_SYNC_NEEDED');return}
 if(!me.ok)throw Error('Account unavailable');
 const user=await me.json();
 if(user.id!==job.uid){await freedomNotify('FREEDOM_SYNC_CONFLICT');return}
 const res=await fetch('/api/sync/state',{method:'PUT',cache:'no-store',credentials:'same-origin',
  headers:{'Content-Type':'application/json'},body:JSON.stringify({expected_version:job.expected_version,data:job.data})});
 if(res.status===409){await freedomNotify('FREEDOM_SYNC_CONFLICT');return}
 if(!res.ok)throw Error('Retry later: '+res.status);
 const result=await res.json();
 await freedomDBOp('meta','readwrite',s=>s.put(result.version,'base:'+job.uid));
 const pending=await freedomDBOp('jobs','readonly',s=>s.get('state'));
 if(pending?.id===job.id)await freedomDBOp('jobs','readwrite',s=>s.delete('state'));
 await freedomNotify('FREEDOM_SYNC_DONE');
}
self.addEventListener('sync',event=>{if(event.tag==='freedom-realty-upload')event.waitUntil(freedomSync())});
