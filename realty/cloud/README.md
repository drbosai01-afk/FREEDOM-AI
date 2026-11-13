# FREEDOM REALTY — API PostgreSQL и синхронизация

**Статус:** серверный код и синтетические тесты готовы; постоянная PostgreSQL и SMTP пока не подключены. Не использовать реальные клиентские данные до отдельного выпуска с проверкой безопасности и защиты данных. Действующий Блокнот: https://bloknot-rieltora-krasnodar.vercel.app/index.html — **не заменён облачной версией**.

## Реализовано в коде

- Email и пароль (Argon2); в production вход возможен только после подтверждения email одноразовой ссылкой (24 часа). SMTP-доставка требует защищённых переменных окружения; повторная отправка ограничена.
- 12-часовой JWT, в production также HttpOnly/Secure/SameSite=Strict cookie для Service Worker; для cookie-записей включена проверка Origin.
- Ограничение попыток регистрации и входа через таблицу PostgreSQL и advisory-lock для конкурентных серверов.
- Разделение записей по аккаунтам; полное состояние Блокнота сохраняется без потери неизвестных полей, с проверкой уникальности ID, SHA-256, защитой от конфликтов версий (409) и историей.
- Большие JSON передаются частями по 128 KiB (обычные запросы не смогут надёжно отправить каталог 7 МБ целиком через Vercel).
- Alembic-миграции `0001_initial` и `0002_catalog_entries`; destructive downgrade отключён.
- Исходный каталог 1161/532/96 можно экспортировать и импортировать в отдельную таблицу с проверкой количества, сухим прогоном и запретом перезаписи ID.
- Опциональный офлайн-модуль `cloud-offline.js` сохраняет несинхронизированные изменения в IndexedDB, а `sw-cloud-extension.js` реализует попытку Background Sync при поддержке браузером. При конфликте база не стирается.
- `/api/health` возвращает HTTP 200 только когда в production доступны PostgreSQL, нужная версия миграций, SMTP и HTTPS URL. Иначе HTTP 503.

## Локальное тестирование на синтетических данных

```bash
cd realty/cloud
python -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
export JWT_SECRET="$(python -c 'import secrets;print(secrets.token_urlsafe(48))')"
python -m pytest -q
uvicorn main:app --host 127.0.0.1 --port 8000
```

SQLite допустима **только локально или в тестах**. Для теста миграций на чистой БД:

```bash
export FREEDOM_MIGRATING=1
export DATABASE_URL=sqlite:///./migration-test.db
python -m alembic -c alembic.ini upgrade head
```

## Production-настройка — не выполнена

1. Создать долговечную PostgreSQL в Neon/Vercel или ином провайдере, включить TLS и backup/restore; не использовать SQLite в Vercel.
2. Указать `ENVIRONMENT=production`, защищённые `DATABASE_URL`, `JWT_SECRET` (не короче 48 символов), `PUBLIC_BASE_URL=https://…`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` в защищённых переменных сервера. Ничего из этого не публиковать в JS, GitHub и логах.
3. На PostgreSQL запустить `python -m alembic -c alembic.ini upgrade head` и убедиться в `alembic_version=0002_catalog_entries`.
4. Развернуть API на публичном HTTPS-origin и проверить `GET /api/health`: HTTP 200, `ready:true`. До этого запрещён ввод реальных данных.
5. Для наполненного каталога сначала подтвердить уже сделанный серверный seed backup, затем выполнить `node scripts/export_legacy_seed.mjs /safe/data.js /secure/catalog.json` на закрытом устройстве; `python -m scripts.import_catalog /secure/catalog.json` — **только сухой прогон**. Параметры `--apply --confirm-sha` разрешать только после проверки источника и обновлённой копии PostgreSQL.
6. Для локальных записей телефона: после входа подтвердить сравнение `IndexedDB['krasnodar-notebook']['store']['state']` с облаком и только затем вручную отправить проверенную копию через chunked endpoint. Личные данные из телефона сервер удалённо не читает.
7. Подключать `cloud-sync-addon.js`, `cloud-offline.js` и объединённый service worker **только после** проверки на двух Android-устройствах: офлайн, повтор, истёкший сеанс, конфликт версий, восстановление, отсутствие сети.
8. Проверить требования по согласию на обработку персональных данных, ограничения хранения, мониторинг ошибок и восстановление после отказа. После этого разрешить выпуск.

## CI и история релиза

- GitHub workflow `.github/workflows/realty-tests.yml`: синтетические тесты, синтаксис JavaScript, проверка Python и миграция на отдельной временной PostgreSQL 17.
- Тестовая Vercel-сборка `freedom-realty-api-ci` не является рабочим сервером пользователей.
- Исходный каталог сохранён в private Blob; хеш и результаты проверки: `realty/RELEASE_GATE.md`.
- Существующий старый способ импорта 105 объектов оставлен лишь для обратной совместимости, это **не** полная миграция актуальных 1161 объектов.

**Правило выпуска:** не применять реальные персональные данные до завершения защиты и проверки CI; при любых конфликтах оставлять локальную исходную базу без изменений.
