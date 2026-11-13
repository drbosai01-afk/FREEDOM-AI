/* FREEDOM REALTY Agent Desk v1: local-only UI. Never mutates notebook database. */
(()=>{'use strict';
const ID='fr-agent-desk';
const htmlEscape=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'}[c]));
const clean=v=>String(v??'').normalize('NFKC').replace(/[\u200B-\u200D\uFEFF]/g,'').replace(/[★☆✓✔✅🔹◆■●◼▸►→⬇️]/gu,' ').replace(/([!?,.;:])\1{1,}/g,'$1').replace(/\s*[|¦]+\s*/g,' · ').replace(/[ \t]{2,}/g,' ').replace(/\n{3,}/g,'\n\n').trim().slice(0,1300);
const money=v=>Number.isFinite(Number(v))&&Number(v)>0?new Intl.NumberFormat('ru-RU',{maximumFractionDigits:0}).format(Number(v))+' ₽':'Цена по запросу';
const saneUrl=url=>{try{const u=new URL(String(url));return ['https:','http:'].includes(u.protocol)?u.href:''}catch{return ''}};
const sanePhone=x=>String(x??'').replace(/[^0-9+]/g,'');
const distinct=a=>[...new Set(a.filter(Boolean))];
const label=v=>clean(v||'Не указан');
let state=null,filtered=[],page=0,groupMode='none',activeFolder='catalog';
function getState(){
 return new Promise((resolve,reject)=>{
  if(!('indexedDB' in window)){try{resolve(JSON.parse(localStorage.getItem('realtor-state')||'null'))}catch(e){reject(e)}return}
  const request=indexedDB.open('krasnodar-notebook');
  request.onerror=()=>{try{resolve(JSON.parse(localStorage.getItem('realtor-state')||'null'))}catch(e){reject(e)}};
  request.onsuccess=()=>{
   const db=request.result;
   if(!db.objectStoreNames.contains('store')){db.close();resolve(window.SEED?{properties:window.SEED.properties||[],queue:window.SEED.pendingProperties||[],sources:window.SEED.sources||[]}:null);return}
   const req=db.transaction('store','readonly').objectStore('store').get('state');
   req.onsuccess=()=>{db.close();resolve(req.result||null)};
   req.onerror=()=>{db.close();reject(req.error)};
  };
 });
}
const contacts=p=>{
 const src=(state?.sources||[]).find(s=>s.id===p.sourceId);
 const phones=distinct([...(Array.isArray(p.phones)?p.phones:[]),...(Array.isArray(src?.phones)?src.phones:[]),src?.contact,src?.contacts].filter(Boolean).flatMap(v=>Array.isArray(v)?v:[v]).map(x=>typeof x==='string'?x:x?.phone||'').filter(v=>sanePhone(v).replace(/\D/g,'').length>=10));
 return phones;
};
const hasContact=p=>contacts(p).length>0;
const n=v=>Number(v)||0;
const district=p=>label(p.district||p.address?.split(',')?.[0]||'Район не указан');
const condition=p=>label(p.condition||'Не указано');
const priceBand=p=>{const v=n(p.priceRub);return !v?'Без цены':v<4000000?'До 4 млн':v<6000000?'4–6 млн':v<9000000?'6–9 млн':'От 9 млн'};
const sortBy={
 newest:(a,b)=>Date.parse(b.updatedAt||b.postedAt||0)-Date.parse(a.updatedAt||a.postedAt||0),
 cheap:(a,b)=>(n(a.priceRub)||Infinity)-(n(b.priceRub)||Infinity),
 expensive:(a,b)=>n(b.priceRub)-n(a.priceRub),
 area:(a,b)=>n(b.areaM2)-n(a.areaM2)
};
function row(p){
 const tel=contacts(p)[0],link=saneUrl(p.sourceUrl)||(Array.isArray(p.sources)?p.sources.map(x=>saneUrl(x?.url)).find(Boolean):'');
 const desc=clean(p.notes||p.rawText||'');
 const flags=Array.isArray(p.flags)?p.flags.map(clean).filter(Boolean).slice(0,4):[];
 return '<article class="fr-item"><div class="fr-card-top"><strong>'+htmlEscape(clean(p.title||p.address||'Объект недвижимости'))+'</strong><b>'+htmlEscape(money(p.priceRub))+'</b></div>'+
 '<div class="fr-tags"><span>'+htmlEscape(district(p))+'</span><span>'+htmlEscape(label(p.rooms||p.type))+'</span><span>'+htmlEscape(condition(p))+'</span><span>'+htmlEscape(String(p.areaM2||'?'))+' м²</span>'+
 flags.map(f=>'<span>'+htmlEscape(f)+'</span>').join('')+'</div>'+
 '<p class="fr-address">'+htmlEscape(clean(p.address||'Адрес уточняется'))+'</p>'+
 (desc?'<p class="fr-description">'+htmlEscape(desc.slice(0,280))+'</p>':'')+
 '<div class="fr-actions">'+(tel?'<a href="tel:'+htmlEscape(sanePhone(tel))+'">Позвонить</a>':'<span class="fr-no-contact">Нет контакта</span>')+
 (link?'<a href="'+htmlEscape(link)+'" target="_blank" rel="noopener noreferrer">Источник</a>':'')+
 '<button type="button" data-copy="'+htmlEscape(p.id)+'">Скопировать</button></div></article>';
}
function opts(id,list){const node=document.getElementById(id),value=node.value;node.innerHTML='<option value="">Все</option>'+list.map(x=>'<option value="'+htmlEscape(x)+'">'+htmlEscape(x)+'</option>').join('');node.value=value}
function render(){
 if(!state)return;
 const values=document.getElementById('fr-query').value.toLocaleLowerCase('ru');
 const region=document.getElementById('fr-district').value,cond=document.getElementById('fr-condition').value,band=document.getElementById('fr-price').value,rooms=document.getElementById('fr-rooms').value;
 const base=activeFolder==='queue'?(state.queue||[]):(state.properties||[]);
 filtered=base.filter(p=>{
  if(activeFolder==='nocontact'&&hasContact(p))return false;
  if(region&&district(p)!==region)return false;
  if(cond&&condition(p)!==cond)return false;
  if(band&&priceBand(p)!==band)return false;
  if(rooms&&String(p.rooms||p.type||'')!==rooms)return false;
  if(values&&!['title','address','district','condition','rawText','notes','sourceName','type','priceRaw'].some(k=>clean(p[k]).toLocaleLowerCase('ru').includes(values)))return false;
  return true;
 }).sort(sortBy[document.getElementById('fr-sort').value]||sortBy.newest);
 document.getElementById('fr-total').textContent=filtered.length+' объектов';
 document.getElementById('fr-nav').innerHTML=['catalog','nocontact','queue'].map((key,i)=>{
  const count=key==='catalog'?(state.properties||[]).length:key==='nocontact'?(state.properties||[]).filter(p=>!hasContact(p)).length:(state.queue||[]).length;
  const names=['Все объекты','Без контактов','На разборе'];
  return '<button type="button" class="'+(key===activeFolder?'fr-active':'')+'" data-folder="'+key+'">'+htmlEscape(names[i])+' <small>'+count+'</small></button>';
 }).join('');
 showPage();
}
function showPage(){
 const root=document.getElementById('fr-results'),size=35;
 const list=filtered.slice(page*size,(page+1)*size);
 if(groupMode==='none')root.innerHTML=list.map(row).join('')||'<p class="fr-empty">По указанным критериям объекты не найдены. Измени фильтры.</p>';
 else {
  const key=groupMode==='district'?district:groupMode==='condition'?condition:priceBand;
  const groups=new Map();
  for(const item of list){const label=key(item);if(!groups.has(label))groups.set(label,[]);groups.get(label).push(item)}
  root.innerHTML=[...groups.entries()].map(([name,items])=>'<section class="fr-group"><h3>'+htmlEscape(name)+' <small>'+items.length+'</small></h3>'+items.map(row).join('')+'</section>').join('')||'<p class="fr-empty">Ничего не найдено</p>';
 }
 const totalPages=Math.max(1,Math.ceil(filtered.length/size));
 document.getElementById('fr-pagination').innerHTML='<button type="button" id="fr-prev" '+(page<1?'disabled':'')+'>Назад</button><span>'+Math.min(page+1,totalPages)+' / '+totalPages+'</span><button type="button" id="fr-next" '+(page+1>=totalPages?'disabled':'')+'>Далее</button>';
 document.getElementById('fr-prev').onclick=()=>{page--;showPage();document.getElementById('fr-content').scrollTop=0};
 document.getElementById('fr-next').onclick=()=>{page++;showPage();document.getElementById('fr-content').scrollTop=0};
 root.querySelectorAll('[data-copy]').forEach(btn=>btn.onclick=()=>{
  const p=filtered.find(p=>p.id===btn.dataset.copy);
  if(!p)return;
  const msg=[clean(p.title||'Объект недвижимости'),clean(p.address||''),money(p.priceRub),clean(p.condition||''),saneUrl(p.sourceUrl)].filter(Boolean).join('\n');
  navigator.clipboard.writeText(msg).then(()=>{btn.textContent='Скопировано';setTimeout(()=>btn.textContent='Скопировать',1800)}).catch(()=>{btn.textContent='Ошибка копирования'});
 });
}
function redraw(){page=0;render()}
async function refresh(){
 try{
  const fresh=await getState();
  if(!fresh||!Array.isArray(fresh.properties))throw Error('Каталог пока не загрузился');
  state=fresh;
  opts('fr-district',distinct([...(state.properties||[]),...(state.queue||[])].map(district)).sort((a,b)=>a.localeCompare(b,'ru')));
  opts('fr-condition',distinct([...(state.properties||[]),...(state.queue||[])].map(condition)).sort((a,b)=>a.localeCompare(b,'ru')));
  opts('fr-rooms',distinct([...(state.properties||[]),...(state.queue||[])].map(p=>String(p.rooms||p.type||'')).filter(Boolean)).sort((a,b)=>a.localeCompare(b,'ru')));
  redraw();
 }catch(e){document.getElementById('fr-results').innerHTML='<p class="fr-empty">'+htmlEscape(e.message)+'</p>'}
}
const screen=document.createElement('section');screen.id=ID;screen.hidden=true;screen.setAttribute('aria-label','Рабочее место риелтора');
screen.innerHTML='<div class="fr-head"><div><small>FREEDOM REALTY</small><h2>Каталог риелтора</h2></div><button id="fr-close" type="button" aria-label="Закрыть">✕</button></div>'+
 '<div id="fr-nav" class="fr-nav" role="tablist"></div><div class="fr-filters"><label>Поиск по ЖК, адресу и описанию<input id="fr-query" placeholder="Например: Метальникова, 2-комн, 5 млн"></label>'+
 '<label>Район<select id="fr-district"><option value="">Все</option></select></label><label>Цена<select id="fr-price"><option value="">Любая</option><option>До 4 млн</option><option>4–6 млн</option><option>6–9 млн</option><option>От 9 млн</option><option>Без цены</option></select></label>'+
 '<label>Комнатность<select id="fr-rooms"><option value="">Любая</option></select></label><label>Состояние<select id="fr-condition"><option value="">Любое</option></select></label>'+
 '<label>Сортировать<select id="fr-sort"><option value="newest">Сначала обновлённые</option><option value="cheap">Сначала дешевле</option><option value="expensive">Сначала дороже</option><option value="area">По площади</option></select></label>'+
 '<label>Группировка<select id="fr-group"><option value="none">Без групп</option><option value="district">По районам</option><option value="price">По цене</option><option value="condition">По состоянию</option></select></label>'+
 '<button type="button" id="fr-reset">Сбросить</button><button type="button" id="fr-refresh">Обновить</button></div>'+
 '<div class="fr-summary"><strong id="fr-total">Загрузка каталога…</strong><small>Цены и наличие проверяйте по источнику. Оригинальные записи не изменяются.</small></div>'+
 '<div id="fr-content"><div id="fr-results"></div><div id="fr-pagination"></div></div>';
document.body.appendChild(screen);
const launch=document.createElement('button');launch.id='fr-launch';launch.type='button';launch.textContent='Каталог PRO';launch.setAttribute('aria-label','Открыть профессиональный каталог');document.body.appendChild(launch);
launch.onclick=()=>{screen.hidden=false;launch.hidden=true;document.body.classList.add('fr-open');refresh()};
document.getElementById('fr-close').onclick=()=>{screen.hidden=true;launch.hidden=false;document.body.classList.remove('fr-open')};
screen.querySelectorAll('input,select').forEach(x=>x.addEventListener('input',()=>{groupMode=document.getElementById('fr-group').value;redraw()}));
document.getElementById('fr-reset').onclick=()=>{screen.querySelectorAll('input,select').forEach(e=>e.value='');groupMode='none';redraw()};
document.getElementById('fr-refresh').onclick=refresh;
document.getElementById('fr-nav').onclick=e=>{const node=e.target.closest('[data-folder]');if(!node)return;activeFolder=node.dataset.folder;redraw()};
})();
