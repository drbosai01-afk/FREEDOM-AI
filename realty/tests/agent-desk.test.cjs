'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {JSDOM}=require('jsdom');
const {indexedDB}=require('fake-indexeddb');
const root=path.resolve(__dirname,'..');
const makeProperty=i=>({
 id:'p'+i,
 title:i%2?'Студия':'2-комнатная квартира',
 address:i%3?'Краснодар, Петра Метальникова':'Краснодар, ул. Дубравная',
 district:i%3?'Метальникова':'Дубравная',
 rooms:i%2?'Студия':'2',
 priceRub:3800000+i*2500,
 areaM2:24+i%65,
 floor:i%20+1,
 condition:i%2?'С ремонтом':'Предчистовая',
 phones:i%4===0?['+79990000000']:[],
 rawText:'★ Новая квартира!!!   Срочно!!!'
});
async function run(){
 const properties=Array.from({length:1161},(_,i)=>makeProperty(i));
 const queue=Array.from({length:532},(_,i)=>({...makeProperty(i),id:'q'+i}));
 const sources=Array.from({length:96},(_,i)=>({id:'source'+i,name:'Источник '+i}));
 const dom=new JSDOM('<!doctype html><html><body></body></html>',{url:'https://example.test/',runScripts:'outside-only'});
 const w=dom.window;w.indexedDB=indexedDB;
 const req=indexedDB.open('krasnodar-notebook',1);
 await new Promise((resolve,reject)=>{
   req.onupgradeneeded=()=>req.result.createObjectStore('store');
   req.onsuccess=()=>{
    const db=req.result,tx=db.transaction('store','readwrite');
    tx.objectStore('store').put({properties,queue,sources,clients:[],collections:[],notes:[],showings:[]},'state');
    tx.oncomplete=()=>{db.close();resolve()};
    tx.onerror=()=>reject(tx.error);
   };
   req.onerror=()=>reject(req.error);
 });
 w.eval(fs.readFileSync(path.join(root,'agent-desk.js'),'utf8'));
 const doc=w.document;
 assert.equal(doc.querySelectorAll('#fr-launch').length,1);
 doc.getElementById('fr-launch').click();
 await new Promise(r=>setTimeout(r,80));
 assert.match(doc.getElementById('fr-total').textContent,/1161/);
 assert.equal(doc.querySelectorAll('.fr-item').length,35);
 assert.equal(doc.querySelectorAll('.fr-item strong').length,35);
 const min=doc.getElementById('fr-min-price'),max=doc.getElementById('fr-max-price');
 min.value='5';max.value='6';max.dispatchEvent(new w.Event('input',{bubbles:true}));
 const expected=properties.filter(x=>x.priceRub>=5000000&&x.priceRub<=6000000).length;
 assert.equal(Number(doc.getElementById('fr-total').textContent.split(' ')[0]),expected);
 doc.getElementById('fr-reset').click();
 doc.querySelector('[data-folder="nocontact"]').click();
 const missing=properties.filter(p=>!p.phones.length).length;
 assert.equal(Number(doc.getElementById('fr-total').textContent.split(' ')[0]),missing);
 assert.equal(doc.querySelectorAll('.fr-item a[href^="tel:"]').length,0);
 doc.querySelector('[data-folder="queue"]').click();
 assert.match(doc.getElementById('fr-total').textContent,/532/);
 doc.querySelector('[data-folder="catalog"]').click();
 const floor=doc.getElementById('fr-max-floor');
 floor.value='5';floor.dispatchEvent(new w.Event('input',{bubbles:true}));
 const low=properties.filter(p=>p.floor<=5).length;
 assert.equal(Number(doc.getElementById('fr-total').textContent.split(' ')[0]),low);
 assert.equal(doc.querySelectorAll('.fr-item').length,35);
 assert.equal(properties[0].rawText,'★ Новая квартира!!!   Срочно!!!'); // no writeback
 console.log(JSON.stringify({pass:true,catalog:1161,queue:532,sources:96,withoutContacts:missing,budgetMatches:expected,lowFloor:low}));
 dom.window.close();
}
run().catch(e=>{console.error(e.stack);process.exitCode=1});
