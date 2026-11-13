# FREEDOM REALTY — фактическое состояние внедрения (13.11.2026)

## Проверенный серверный резерв исходного каталога
- Исходный сайт: https://bloknot-rieltora-krasnodar.vercel.app/index.html
- Исходный deployment: `dpl_5mjPXwMLF1tqwJhgem4bGmnkGee8`, целевой production, без замены
- Исходный ресурс: `data.js` — 7 213 688 байт
- SHA-256: `187dfd2f0bc03c2b174f8c6df223015fe6932491cad718b06d6b57edfedbbafb`
- Vercel private Blob store: `store_HOIAKJ2PplowZ6uL` (`fra1`)
- Серверный архив: `original-seed/187dfd2f0bc03c2b174f8c6df223015fe6932491cad718b06d6b57edfedbbafb.js`
- Подтверждено через Vercel build log: файл загружен, повторно прочитан и проверен по SHA-256.
- Подтверждено через Vercel storage API: статус available, один объект, размер 7 213 688 байт.

## Предварительная сборка
- Vercel deployment: `dpl_Arc12Yfk5kEKmug4F6iMgHuwGgvx`, READY (preview).
- В preview сохранён тот же бинарный `data.js` (SHA-1 `b98b6dd85e32aae3dfd32520c28f8cd001272755`).
- Экспорт Android: добавлен адаптер Web Share с возвратом к исходной загрузке при ошибке.
- Статус сборки READY не доказывает прохождение пользовательских сценариев на Android.

## Пока не сделано (не выдавать за готовое)
- Нет подтверждённой резервной копии IndexedDB/LocalStorage конкретного телефона.
- Число 1161 — показатель UI пользователя, пока независимо не пересчитаны объекты внутри исходного JS.
- Полноценное API авторизации и PostgreSQL не развёрнуто в production.
- Облачная синхронизация объектов, клиентов, фотографий и показов между устройствами не активирована.
- Не переносить/не заменять production до резервной копии локальных изменений, сверки схемы, контроля дублей и E2E проверки на Android.

## Безопасность
- Ни Blob token, ни API ключи не помещать в репозиторий, фронтенд или отчёты.
- Закрытое хранилище подключено к Vercel через защищённую переменную `BLOB_READ_WRITE_TOKEN`.
- Превышение бесплатных лимитов Vercel может повлечь расход, отслеживать usage.


## Обновление основного адреса
- Production deployment: `dpl_G4E5yM6EbkoUVbkSCMFw26V33sFz` — READY.
- Подтверждено: домен `bloknot-rieltora-krasnodar.vercel.app` теперь указывает на этот deployment.
- Проверено по хешам: оригинальные `data.js`, `app.js`, `core.js` перенесены без изменения.
- Сохранены 1161 `window.SEED.properties`, 532 `window.SEED.pendingProperties`, 96 `window.SEED.sources` по read-only аудиту.
- Добавлены `export-share.js` (native Android Share с fallback на старый экспорт), обновлён SW-cache, `/api/health` (проверяет наличие конфигурации хранилища, без записи).
- Прежний production deployment: `dpl_5mjPXwMLF1tqwJhgem4bGmnkGee8` — возможный вариант отката.
- **Не путать:** новый production не синхронизирует личные IndexedDB-записи между телефонами; сервер хранит лишь проверенную копию встроенного исходного каталога. Не заявлять, что двухсторонняя синхронизация готова.
