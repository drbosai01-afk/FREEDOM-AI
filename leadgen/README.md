# FREEDOM LEADS v2 — full-stack lead capture + CRM

Self-hostable, Russian-language independent SaaS foundation inspired by the user's local demo; **not a verified reproduction of leadogen.ai** (site could not be retrieved).

## Features implemented

- Responsive CRM for mobile Chrome and desktop, standalone web app manifest, login, registration and logout.
- Argon2 hashing, signed HttpOnly secure cookies with server-side session revocation, strict same-origin checks for writes, per-tenant row-level filtering.
- **Production-mode email verification and password reset** using configured SMTP, rate-limited endpoints; development mode skips email confirmation for quick local evaluation.
- Leads: create, deduplicate by source + phone, update status, budget and tags; notes and immutable event log; source/UTM tracking; pipeline; CSV export and analytics.
- Lead sources: unique public form URL, webhook with one-time API key, source activation/deactivation, opt-in consent, anti-bot honeypot, per-IP/slug throttling.
- Follow-up tasks, per-account isolation, rule-based lead score, server-side Telegram bot notifications when configured.
- Interactive OpenAPI docs at `/docs`; Dockerfile and FastAPI test suite.

## Start locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export ENVIRONMENT=development
export DATABASE_URL=sqlite:///./leads.sqlite
uvicorn main:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000. On Windows activate `.venv\\Scripts\\activate` instead. To test: `pytest -q` from project root (requires `pytest`, `httpx`).

## Required for real production

1. Provision independent persistent PostgreSQL with TLS, automatic backup/restore, versioned schema migration and backups before upgrades. **Do not use SQLite on serverless Vercel**. Code currently creates missing tables; before rolling schema changes to an existing production DB use reviewed Alembic migrations.
2. Set `ENVIRONMENT=production`, `DATABASE_URL`, a random 48+ char `JWT_SECRET`, and verified `PUBLIC_BASE_URL=https://…` in **server-side secrets**, not GitHub, frontend or logs.
3. Set SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM on the server; verify activation and reset email delivery using a test account. Publishing real signup before this will leave users unverified.
4. Configure HTTPS reverse proxy, backups, monitoring, request logs that exclude secret tokens and personal details, reliable DB migrations and disaster recovery tests.
5. Publish a privacy policy and personal-data handling agreement appropriate to the actual business, jurisdiction and owner; provide consent withdrawal and data deletion process. **Do not collect personal customer information until this is done.**
6. Load-test throttling and run security audit, including XSS/CSRF, email enumeration, data exfiltration, password reset, duplicate handling and concurrent write behavior.
7. For VK/Yandex/native Telegram lead imports, register and authorize each official API integration. The app already supports **source-specific webhook ingress and UTM-tagged URLs**, but it does not silently access advertising accounts or scrape platforms.

## API examples

Create a source from CRM, copy the one-time `X-API-Key` and POST JSON to its webhook:

```bash
curl -X POST 'https://YOUR-DOMAIN/api/webhook/YOUR-SLUG' \\
  -H 'Content-Type: application/json' -H 'X-API-Key: YOUR-SERVER-KEY' \\
  -d '{"name":"Тест","phone":"+79990000000","utm_source":"vk","utm_campaign":"autumn","consent":true}'
```

Never put the webhook secret into a public HTML page or client-side ad creative. Public no-key traffic must use the `/f/SLUG` form, not the webhook.

## Delivery scope

This is a **working deployable source package**, not proof of a published commercial SaaS. There is no billing, AI model integration, employee roles, native Android APK, official VK/Yandex OAuth integration, or provider-certified GDPR/152-FZ compliance at present. All those need separate integration, security and business verification.
