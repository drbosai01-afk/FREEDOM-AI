/* FREEDOM REALTY opt-in cloud sync adapter.
 * Reads the existing IndexedDB state without changing the original data model.
 * Disabled unless a compatible HTTPS API exists on the SAME origin.
 * Never auto-overwrites local records; a recovery copy is required before restore.
 */
(() => {
  'use strict';
  const API = '/api/';
  const FIELDS = ['properties','queue','clients','collections','notes','showings','sources'];
  const el = (name) => document.getElementById(name);
  let token = sessionStorage.getItem('freedom-realty-token') || '';
  let remote = null;
  let local = null;
  const counts = (v) => Object.fromEntries(FIELDS.map(k => [k, Array.isArray(v?.[k]) ? v[k].length : -1]));
  const status = (text) => { const t = el('fr-status'); if(t) t.textContent = text; };
  function valid(data) {
    if (!data || FIELDS.some(k => !Array.isArray(data[k]))) throw Error('Неполная структура Блокнота');
    for (const k of FIELDS) {
      const ids = data[k].map(x => x?.id);
      if (ids.some(x => !x || typeof x !== 'string') || new Set(ids).size !== ids.length) throw Error('Ошибка идентификаторов: '+k);
    }
    return data;
  }
  async function openStore() {
    return new Promise((resolve,reject)=>{
      const r=indexedDB.open('krasnodar-notebook');
      r.onsuccess=()=>{const db=r.result;if(!db.objectStoreNames.contains('store')){db.close();reject(Error('Локальная база не найдена'));return}resolve(db)};
      r.onerror=()=>reject(r.error);
    });
  }
  async function readState() {
    try {
      const db=await openStore();
      try { const data=await new Promise((resolve,reject)=>{
        const r=db.transaction('store','readonly').objectStore('store').get('state');
        r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error);
      }); if(data)return valid(data) } finally { db.close() }
    } catch(e) { /* The original notebook also supports localStorage fallback. */ }
    const backup=localStorage.getItem('realtor-state');
    if(!backup)throw Error('Нет локальной базы для передачи');
    return valid(JSON.parse(backup));
  }
  async function writeRecoveryThenRestore(next) {
    valid(next);
    const db=await openStore();
    try {
      await new Promise((resolve,reject)=>{
        const tx=db.transaction('store','readwrite');
        const store=tx.objectStore('store');
        store.put(local, 'pre-cloud-'+Date.now());
        store.put(next,'state');
        tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error);tx.onabort=()=>reject(tx.error);
      });
    } finally {db.close()}
  }
  async function api(path, method='GET', data) {
    const r=await fetch(API+path,{method,cache:'no-store',headers:{
      'Content-Type':'application/json',...(token?{'Authorization':'Bearer '+token}:{})
    },...(data!==undefined?{body:JSON.stringify(data)}:{})});
    const j=await r.json().catch(()=>({}));
    if(!r.ok)throw Error(typeof j.detail==='string'?j.detail:'Ошибка сервера '+r.status);
    return j;
  }
  const ui=`<details id="freedom-cloud" style="position:fixed;bottom:84px;right:10px;z-index:9998;background:#fff;border:1px solid #8ea9ce;border-radius:14px;box-shadow:0 2px 14px #0002;padding:12px;max-width:min(94vw,380px);font:14px system-ui;color:#172b49">
    <summary style="font-weight:700;cursor:pointer">☁ FREEDOM — облако</summary>
    <p>Ручная синхронизация без удаления данных. Сначала войдите в облачный аккаунт.</p>
    <input id="fr-email" type="email" placeholder="Email" autocomplete="username" style="width:100%;padding:10px;box-sizing:border-box;margin:4px 0">
    <input id="fr-pass" type="password" placeholder="Пароль" autocomplete="current-password" style="width:100%;padding:10px;box-sizing:border-box;margin:4px 0">
    <div style="display:flex;gap:6px;flex-wrap:wrap">
      <button type="button" id="fr-login">Войти</button>
      <button type="button" id="fr-register">Регистрация</button>
      <button type="button" id="fr-check">Сравнить</button>
      <button type="button" id="fr-upload">Сохранить в облако</button>
      <button type="button" id="fr-restore">Восстановить с сервера</button>
    </div>
    <p id="fr-status" role="status" style="overflow-wrap:anywhere"></p>
  </details>`;
  document.body.insertAdjacentHTML('beforeend',ui);
  async function auth(mode){
    token='';
    const j=await api(mode,'POST',{email:el('fr-email').value.trim(),password:el('fr-pass').value});
    token=j.access_token;sessionStorage.setItem('freedom-realty-token',token);
    el('fr-pass').value='';status('Вход выполнен');
  }
  for(const [id,mode] of [['fr-login','login'],['fr-register','register']]){
    el(id).onclick=async()=>{try{await auth(mode)}catch(e){status(e.message)}};
  }
  el('fr-check').onclick=async()=>{
    try {
      local=await readState();
      remote=await api('sync/state');
      status('Устройство: '+JSON.stringify(counts(local))+'; сервер: версия '+remote.version+' '+JSON.stringify(counts(remote.data)));
    }catch(e){status(e.message)}
  };
  el('fr-upload').onclick=async()=>{
    try {
      if(!token)throw Error('Сначала войдите');
      local=await readState(); remote=await api('sync/state');
      const n=counts(local);
      const confirmText='Отправить полную локальную базу в аккаунт? '+JSON.stringify(n)+'; версия сервера '+remote.version+'. Если другие устройства меняли данные, сначала сравните.';
      if(!confirm(confirmText))return;
      const j=await api('sync/state','PUT',{expected_version:remote.version,data:local,allow_shrink:false});
      status('Сохранено: версия '+j.version+', SHA-256 '+j.sha256);
    }catch(e){status(e.message)}
  };
  el('fr-restore').onclick=async()=>{
    try {
      if(!token)throw Error('Сначала войдите');
      local=await readState();remote=await api('sync/state');
      if(!remote.data)throw Error('На сервере нет базы');
      valid(remote.data);
      if(!confirm('Внимание: локальные данные будут заменены! Будет сохранена резервная копия в IndexedDB. Сервер: '+JSON.stringify(counts(remote.data))+'; телефон: '+JSON.stringify(counts(local))))return;
      const check=prompt('Для подтверждения напишите ВОССТАНОВИТЬ');
      if(check!=='ВОССТАНОВИТЬ'){status('Отменено');return}
      await writeRecoveryThenRestore(remote.data);
      status('Локальная копия сохранена, данные восстановлены. Перезагрузка…');
      location.reload();
    }catch(e){status(e.message)}
  };
})();