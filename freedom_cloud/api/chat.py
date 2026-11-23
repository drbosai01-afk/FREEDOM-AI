import os, json, urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler

class handler(BaseHTTPRequestHandler):
    def respond(self, status, obj):
        data=json.dumps(obj,ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Cache-Control","no-store")
        self.send_header("Content-Length",str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        key=os.getenv("GROQ_API_KEY")
        access=os.getenv("FREEDOM_ACCESS_TOKEN")
        if not key or not access:
            return self.respond(503,{"error":"Сервер развёрнут. Для работы ИИ необходимо настроить GROQ_API_KEY и FREEDOM_ACCESS_TOKEN в Vercel."})
        import hmac
        supplied=self.headers.get("X-Freedom-Access","")
        if not hmac.compare_digest(supplied,access):
            return self.respond(401,{"error":"Неверный пароль FREEDOM."})
        try:
            n=int(self.headers.get("Content-Length","0"))
            if n<1 or n>12000:
                return self.respond(413,{"error":"Недопустимый размер запроса"})
            payload=json.loads(self.rfile.read(n))
            prompt=payload.get("prompt","")
            if not isinstance(prompt,str) or not prompt.strip() or len(prompt)>8000:
                return self.respond(400,{"error":"Введите задачу длиной до 8000 символов"})
            req_body={
                "model":os.getenv("GROQ_MODEL","openai/gpt-oss-20b"),
                "messages":[{"role":"system","content":"Ты FREEDOM, аккуратный и практичный ИИ-помощник. Отвечай по-русски. Не выдумывай факты, не утверждай о действиях, которые не выполнял."},{"role":"user","content":prompt}],
                "max_completion_tokens":1200,
            }
            req=urllib.request.Request("https://api.groq.com/openai/v1/chat/completions",data=json.dumps(req_body).encode(),method="POST",headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"})
            with urllib.request.urlopen(req,timeout=35) as resp: answer=json.load(resp)
            self.respond(200,{"answer":answer["choices"][0]["message"].get("content","") or "Пустой ответ модели"})
        except urllib.error.HTTPError as ex:
            try:
                info=json.loads(ex.read().decode()).get("error",{})
                reason=str(info.get("code") or info.get("message") or "api_error")[:200]
            except Exception: reason="api_error"
            self.respond(502,{"error":"Groq HTTP "+str(ex.code)+": "+reason})
        except Exception as ex:
            self.respond(502,{"error":"Ошибка сервера: "+type(ex).__name__})
