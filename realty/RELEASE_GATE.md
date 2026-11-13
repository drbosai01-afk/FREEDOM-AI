# FREEDOM REALTY — release gate (13 Nov 2026)

## Already verified
- Frontend HTTPS: https://bloknot-rieltora-krasnodar.vercel.app/index.html — production Vercel, original app files preserved.
- Original seed archive: Vercel Private Blob, 7,213,688 bytes; SHA-256 `187dfd2f0bc03c2b174f8c6df223015fe6932491cad718b06d6b57edfedbbafb`.
- Seed fields inventoried without printing values: 1,161 unique property IDs, 532 unique pending-property IDs, 96 unique source IDs.
- Backend on feature branch has single-use email activation, SMTP-only delivery, DB-backed authentication rate limits, HttpOnly/SameSite cookie auth and cross-origin write rejection.
- Migrations: Alembic `0001_initial` and `0002_catalog_entries`, destructive downgrades disabled.
- No-overwrite catalog importer with dry-run default; preserves complete JSON of original records.
- Large state uploads: chunked SHA-256-verified snapshots + revision-based atomic sync + history.
- Opt-in IndexedDB outbox and Service Worker Background Sync extension written, **not promoted to production**.
- Automated isolated CI includes synthetic API tests and an ephemeral PostgreSQL 17 schema-upgrade check. View latest job status in PR #4.

## NOT complete (do not treat as working)
- No provisioned permanent PostgreSQL/Neon service has been connected to this Vercel project.
- No configured SMTP provider, sender domain or verified operational email deliverability.
- Backend production public HTTPS domain and working `/api/health` readiness have not been verified.
- Original device-local IndexedDB/client records have NOT been transferred; remote tools cannot read device storage.
- Opt-in background sync has not passed real Android two-device offline/concurrency tests.
- The source catalog JSON has not been imported into permanent PostgreSQL.
- Retention policies, monitoring, privacy notices and app security checks require independent review.
- **Do not upload real names, phones or client files to the test deployment.**

## Secure release sequence (no silent overwrites)
1. Provision durable PostgreSQL (Neon or equivalent) in Vercel and configure encrypted `DATABASE_URL` with TLS, `ENVIRONMENT=production`, random `JWT_SECRET` (48+ chars).
2. Configure verified `PUBLIC_BASE_URL=https://…`, SMTP credentials in encrypted server env, never in frontend or GitHub.
3. On the isolated database run `python -m alembic -c alembic.ini upgrade head`. Verify `alembic_version=0002_catalog_entries`; confirm `GET /api/health` returns 200 and ready=true.
4. Import seed only after a separately verified backup; export exact raw source using `scripts/export_legacy_seed.mjs`, run `python -m scripts.import_catalog /secure/catalog.json` (dry-run), compare source counts and hashes. To write, require explicit `ALLOW_CATALOG_IMPORT=YES`, `BACKUP_SEED_SHA256` and `--confirm-sha`; the importer never replaces existing records.
5. Test two **synthetic** accounts on Android Chrome, offline editing, background retry, contradictory edits (409), logout and email confirmation.
6. On user's original phone, opt-in local transfer only after manual comparison; submit chunked snapshot and retain original local recovery version. Never silently restore old cloud data over a device.
7. Review security, monitor PostgreSQL backups and restore drills, cookie/CSRF protections, data retention and privacy rules before real client data.
8. Only after green GitHub CI and checks above, merge PR #4 and promote reviewed production release.

## Existing protected sources
- Original production deployment: `dpl_5mjPXwMLF1tqwJhgem4bGmnkGee8`.
- Verified original seed Blob: `original-seed/187dfd2f0bc03c2b174f8c6df223015fe6932491cad718b06d6b57edfedbbafb.js`.
- Post-export production app deployment: `dpl_G4E5yM6EbkoUVbkSCMFw26V33sFz`.
- Stage test project: `freedom-realty-api-ci` — **not** a persistent customer database.
