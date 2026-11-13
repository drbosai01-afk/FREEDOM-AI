/* Extract exact seed records from existing data.js without accessing device-local data.
   Run locally only; output may contain personal contact fields. Never commit output. */
import fs from 'node:fs';
import crypto from 'node:crypto';
import vm from 'node:vm';
const input=process.argv[2], output=process.argv[3];
if(!input||!output)throw Error('Usage: node scripts/export_legacy_seed.mjs /safe/data.js /secure/catalog.json');
const raw=fs.readFileSync(input);
const ctx={window:{},self:{},globalThis:{}};
try{vm.runInNewContext(raw.toString('utf8'),ctx,{timeout:5000})}catch(e){
 if(!ctx.window.SEED)throw e;
}
const seed=ctx.window.SEED;
const names=['properties','pendingProperties','sources'];
const report={};
for(const name of names){
 const rows=seed?.[name];
 if(!Array.isArray(rows))throw Error('Missing '+name);
 const ids=rows.map(x=>x?.id);
 if(ids.some(x=>!x||typeof x!=='string')||new Set(ids).size!==rows.length)throw Error('Duplicate/missing IDs: '+name);
 report[name]=rows.length;
}
const portable={properties:seed.properties,pendingProperties:seed.pendingProperties,sources:seed.sources};
const serialized=JSON.stringify(portable);
if(!serialized)throw Error('Unable to serialize seed');
fs.writeFileSync(output,serialized,{flag:'wx',mode:0o600});
console.log(JSON.stringify({status:'written',bytes:Buffer.byteLength(serialized),sha256:crypto.createHash('sha256').update(serialized).digest('hex'),counts:report,original_sha256:crypto.createHash('sha256').update(raw).digest('hex')}));
