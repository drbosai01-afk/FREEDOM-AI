"""FREEDOM Cloud bootstrap: browser UI, real OpenAI Responses API, local SQLite memory."""
import os, json, sqlite3, threading, time, urllib.request, urllib.error, html
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path

ROOT=Path(__file__).parent
DB=ROOT/"freedom.db"
LOCK=threading.RLock()
MODEL=os.getenv("FREEDOM_PRIMARY_MODEL","gpt-4.1-mini")
def db_connect():
    db=sqlite3.connect(DB,timeout=15)
    db.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY, ts REAL, role TEXT, content TEXT)")
    return db
def ask(prompt):
    key=os.getenv("OPENAI_API_KEY")
    if not key: raise RuntimeError("OPENAI_API_KEY не передан в Codespace. Проверьте Repository secrets → Codespaces.")
    payload={"model":MODEL,"input":[{"role":"system","content":"Ты FREEDOM: точный, практичный помощник. Не выдавай предположения за факты. Не совершай внешних действий без разрешения."},{"role":"user","content":prompt}],"store":False,"max_output_tokens":1200}
    req=urllib.request.Request("https://api.openai.com/v1/responses",data=json.dumps(payload).encode(),headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"},method="POST")
    try:
        with urllib.request.urlopen(req,timeout=50) as r: data=json.load(r)
    except urllib.error.HTTPError as err:
        raise RuntimeError("Ошибка OpenAI HTTP "+str(err.code)+". Проверьте API-баланс, ключ и права модели.") from None
    parts=[part.get("text","") for item in data.get("output",[]) for part in item.get("content",[]) if part.get("type")=="output_text"]
    return "\n".join(parts).strip() or "Модель не вернула текст."
PAGE='''<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>FREEDOM</title><style>body{background:#101621;color:#e8edf4;font:16px system-ui;margin:auto;max-width:750px;padding:20px}header{font-size:27px;font-weight:750;margin:15px 0}small{color:#9daec7}.card{background:#1b2637;border-radius:15px;padding:16px;margin:12px 0;white-space:pre-wrap}textarea{width:100%;box-sizing:border-box;background:#202d40;color:white;border:1px solid #60718b;border-radius:12px;padding:14px;font:16px system-ui;min-height:100px}button{background:#70a8ff;border:0;border-radius:10px;padding:14px 22px;font-weight:bold;font-size:16px}#status{color:#c3d4ea;margin:15px 0}</style><header>FREEDOM</header><small>Облачная тестовая версия · реальный API · память SQLite</small><div id="status">Проверка подключения...</div><div id="log"></div><textarea id="prompt" placeholder="Напиши задачу FREEDOM"></textarea><p><button id="send" onclick="send()">Отправить</button></p><script>async function send(){const q=document.querySelector('#prompt').value.trim();if(!q)return;const b=document.querySelector('#send');b.disabled=true;document.querySelector('#status').textContent='Обработка...';try{const r=await fetch('/api/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prompt:q})});const d=await r.json();const node=document.createElement('div');node.className='card';node.textContent='Вы: '+q+'\n\nFREEDOM: '+(d.answer||d.error);document.querySelector('#log').prepend(node);document.querySelector('#status').textContent=r.ok?'Готово':'Ошибка';}catch(e){document.querySelector('#status').textContent=String(e)}finally{b.disabled=false}}fetch('/api/health').then(x=>x.json()).then(d=>document.querySelector('#status').textContent=d.key_configured?'API-ключ найден. Можно отправить задачу.':'API-ключ пока не найден в окружении Codespaces.');</script></html>'''
class Handler(BaseHTTPRequestHandler):
    def output(self,code,data,content_type="application/json"):
        raw=data.encode() if isinstance(data,str) else json.dumps(data,ensure_ascii=False).encode()
        self.send_response(code);self.send_header("Content-Type",content_type+"; charset=utf-8");self.send_header("Content-Length",str(len(raw)));self.send_header("Cache-Control","no-store");self.end_headers();self.wfile.write(raw)
    def do_GET(self):
        if self.path=="/": return self.output(200,PAGE,"text/html")
        if self.path=="/api/health": return self.output(200,{"status":"ok","key_configured":bool(os.getenv("OPENAI_API_KEY")),"model":MODEL})
        self.output(404,{"error":"Not found"})
    def do_POST(self):
        if self.path!="/api/ask": return self.output(404,{"error":"Not found"})
        try:
            n=int(self.headers.get("Content-Length","0"))
            if n<=0 or n>16000: return self.output(413,{"error":"Запрос слишком большой"})
            prompt=json.loads(self.rfile.read(n)).get("prompt","")
            if not isinstance(prompt,str) or not prompt.strip() or len(prompt)>8000: return self.output(400,{"error":"Некорректная задача"})
            answer=ask(prompt)
            with LOCK,db_connect() as db:
                db.execute("INSERT INTO messages(ts,role,content) VALUES(?,?,?)",(time.time(),"user",prompt))
                db.execute("INSERT INTO messages(ts,role,content) VALUES(?,?,?)",(time.time(),"assistant",answer))
            self.output(200,{"answer":answer})
        except Exception as e: self.output(502,{"error":str(e)})
if __name__=="__main__":
    with db_connect(): pass
    print("FREEDOM listening on 127.0.0.1:8765",flush=True)
    ThreadingHTTPServer(("127.0.0.1",8765),Handler).serve_forever()
