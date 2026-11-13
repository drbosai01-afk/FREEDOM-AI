/* Дневник риелтора — non-destructive application shell. */
(()=>{'use strict';
const APP='Дневник риелтора';
const routes=[
 ['today','Главная','⌂'],['catalog','Каталог','▦'],['clients','Клиенты','♙'],
 ['collections','Подборки','▤'],['showings','Показы','▣'],['sources','Источники','◉'],
 ['notes','Заметки','✎'],['tools','Калькулятор','▥'],['assistant','ИИ-помощник','✧'],
 ['import','Импорт','⇩'],['settings','Настройки','⚙']
];
const routeToHash=k=>k==='catalog'?'#today':'#'+k;
const $=s=>document.querySelector(s);
const el=(tag,cls,txt)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(txt)n.textContent=txt;return n};
let installPrompt=null;
document.title=APP+' · Краснодар';
const meta=$('meta[name="theme-color"]');if(meta)meta.content='#0959a8';
const bar=el('header','diary-bar');
bar.innerHTML='<div class="diary-brand"><span class="diary-symbol">Д</span><div><strong>Дневник риелтора</strong><small>Краснодар · рабочий кабинет</small></div></div><div class="diary-bar-actions"><button type="button" id="diary-install" title="Установить приложение">Установить</button><button type="button" id="diary-menu-button" aria-label="Открыть меню" aria-expanded="false">☰</button></div>';
document.body.appendChild(bar);
const shade=el('div','diary-shade');shade.hidden=true;document.body.appendChild(shade);
const drawer=el('aside','diary-drawer');drawer.id='diary-drawer';drawer.hidden=true;drawer.setAttribute('aria-label','Разделы приложения');
drawer.innerHTML='<div class="diary-drawer-top"><div><strong>Дневник риелтора</strong><small>Все инструменты в одном месте</small></div><button type="button" id="diary-close" aria-label="Закрыть">✕</button></div><nav class="diary-drawer-list">'+routes.map(([id,title,icon])=>'<button type="button" data-diary-route="'+id+'"><span class="diary-icon">'+icon+'</span><span>'+title+'</span></button>').join('')+'</nav><div class="diary-drawer-foot"><span id="diary-online"></span><p>Каталог и записи остаются на вашем устройстве. Делайте резервные копии в настройках.</p></div>';
document.body.appendChild(drawer);
const dock=el('nav','diary-dock');dock.setAttribute('aria-label','Быстрая навигация');
dock.innerHTML=[['today','Главная','⌂'],['catalog','Каталог','▦'],['clients','Клиенты','♙'],['showings','Показы','▣'],['menu','Ещё','☰']].map(([id,title,icon])=>'<button type="button" data-diary-route="'+id+'"><span>'+icon+'</span><small>'+title+'</small></button>').join('');
document.body.appendChild(dock);
const openMenu=()=>{drawer.hidden=false;shade.hidden=false;$('#diary-menu-button').setAttribute('aria-expanded','true');document.body.classList.add('diary-menu-open')};
const closeMenu=()=>{drawer.hidden=true;shade.hidden=true;$('#diary-menu-button').setAttribute('aria-expanded','false');document.body.classList.remove('diary-menu-open')};
$('#diary-menu-button').onclick=()=>drawer.hidden?openMenu():closeMenu();
$('#diary-close').onclick=closeMenu;shade.onclick=closeMenu;
function navigate(k){
 closeMenu();
 if(k==='menu'){openMenu();return}
 if(k==='catalog'){
  const pro=$('#fr-launch');
  if(pro){pro.click();return}
  location.hash='#today';setTimeout(()=>$('#catalog-search')?.focus(),100);return
 }
 $('#fr-close')?.click();
 location.hash=routeToHash(k);
}
document.addEventListener('click',e=>{const b=e.target.closest('[data-diary-route]');if(b){e.preventDefault();navigate(b.dataset.diaryRoute)}});
function update(){
 const k=location.hash.slice(1).split('/')[0]||'today';
 document.querySelectorAll('[data-diary-route]').forEach(b=>b.classList.toggle('diary-selected',b.dataset.diaryRoute===k));
 $('#diary-online').textContent=navigator.onLine?'● Сеть доступна':'● Офлайн';
}
window.addEventListener('hashchange',update);
window.addEventListener('online',update);window.addEventListener('offline',update);update();
window.addEventListener('beforeinstallprompt',e=>{e.preventDefault();installPrompt=e;$('#diary-install').textContent='Установить'});
window.addEventListener('appinstalled',()=>{$('#diary-install').textContent='Установлено';installPrompt=null});
$('#diary-install').onclick=async()=>{
 if(installPrompt){installPrompt.prompt();await installPrompt.userChoice;installPrompt=null;return}
 const dialog=el('dialog','diary-install-dialog');
 dialog.innerHTML='<h2>Установить Дневник риелтора</h2><p><strong>Android · Chrome:</strong> откройте меню браузера ⋮ → «Установить приложение» или «Добавить на главный экран».</p><p><strong>iPhone · Safari:</strong> «Поделиться» → «На экран Домой».</p><p>Устанавливайте приложение с этого адреса: данные, сохранённые на другом домене, автоматически не переносятся.</p><button type="button">Понятно</button>';
 document.body.appendChild(dialog);dialog.querySelector('button').onclick=()=>{dialog.close();dialog.remove()};dialog.addEventListener('close',()=>dialog.remove());dialog.showModal();
};
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeMenu()});
})();
