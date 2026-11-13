"""Read-only audit of public seed asset. Does not print or upload actual records."""
import hashlib
import json
import re
from urllib.request import Request, urlopen

URL = "https://bloknot-rieltora-krasnodar.vercel.app/data.js"
request = Request(URL, headers={"User-Agent": "FREEDOM-REALTY-Backup-Audit/1.0"})
with urlopen(request, timeout=45) as res:
    if res.status != 200:
        raise SystemExit(f"HTTP {res.status}")
    data = res.read(35_000_000)
    content_type = res.headers.get("content-type", "")
if len(data) < 100 or data.lstrip().lower().startswith(b"<!doctype"):
    raise SystemExit("Asset missing or HTML returned instead of JavaScript")
text = data.decode("utf-8")
print(json.dumps({
    "url": URL,
    "asset": "data.js",
    "bytes": len(data),
    "sha256": hashlib.sha256(data).hexdigest(),
    "content_type": content_type,
    "preview_first_400_chars_redacted": re.sub(r'[0-9A-Za-z]', 'X', text[:400]),
    "seed_object_indicator_counts": {
        "sourceId": len(re.findall(r'"sourceId"\s*:', text)),
        "externalId": len(re.findall(r'"externalId"\s*:', text)),
        "title": len(re.findall(r'"title"\s*:', text)),
    },
}, ensure_ascii=False, indent=2))
