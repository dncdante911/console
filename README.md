# MiniHost Panel

Понял задачу: установить на **чистую Ubuntu**, управлять через веб-интерфейс и иметь **отдельный сервер лицензий**.
Этот репозиторий теперь включает оба компонента:

1. `app/` — панель управления хостингом.
2. `license_server/` — отдельный API-сервер лицензий.

## Что работает сейчас

- Веб-панель: сайты, SSL (через генерацию certbot команды), почтовые домены/ящики.
- Проверка лицензии перед изменяющими операциями.
- Отдельный license server:
  - выпуск лицензии,
  - ревокация лицензии,
  - валидация лицензии + привязка к machine id.
- Установка на Ubuntu через один скрипт `scripts/setup_ubuntu.sh` в режимах `panel` и `license`.

---

## 1) Схема прод-развёртывания

- **Сервер A (панель)**: Ubuntu + Nginx/Certbot/Postfix/Dovecot + MiniHost Panel.
- **Сервер B (лицензии)**: Ubuntu + MiniHost License Server.
- Панель хранит `license_server_url` и `license_key`, и валидирует лицензию через API.

---

## 2) Установка на чистую Ubuntu (сервер лицензий)

На сервере B:

```bash
git clone <YOUR_REPO_URL> minihost
cd minihost
export LICENSE_API_TOKEN='super-secret-token'
./scripts/setup_ubuntu.sh license
```

Проверка:

```bash
curl http://127.0.0.1:8099/health
```

### Выпуск лицензии

```bash
curl -X POST http://127.0.0.1:8099/api/v1/issue \
  -H 'Content-Type: application/json' \
  -d '{
    "api_token":"super-secret-token",
    "license_key":"LIC-TEST-0001",
    "max_activations":1
  }'
```

---

## 3) Установка на чистую Ubuntu (сервер панели)

На сервере A:

```bash
git clone <YOUR_REPO_URL> minihost
cd minihost
./scripts/setup_ubuntu.sh panel
```

Открыть панель: `http://SERVER_IP:8088`

В UI в разделе **Лицензия**:
- `server_url`: `http://LICENSE_SERVER_IP:8099`
- `license_key`: `LIC-TEST-0001`

После активации можно создавать сайты/почту и запускать операции.

---

## 4) Как это работает внутри

### Панель (`app/main.py`)

- При открытии дашборда показывает текущий статус лицензии.
- Изменяющие операции (`создание сайта`, `SSL`, `почта`, `reload nginx`) требуют активной лицензии.
- Настройки лицензии хранятся в SQLite таблице `settings`.

### Лиценз-сервер (`license_server/main.py`)

- `/api/v1/issue` — создать/обновить лицензию (с API-токеном).
- `/api/v1/revoke` — отозвать лицензию.
- `/api/v1/validate` — проверить лицензию и machine id.

---

## 5) Важные файлы

- `app/main.py` — роуты панели и лиценз-проверка.
- `app/db.py` — SQLite + settings.
- `app/services/license.py` — клиент лицензирования для панели.
- `license_server/main.py` — API сервера лицензий.
- `scripts/setup_ubuntu.sh` — автоматическая установка.

---

## 6) Что нужно добавить для уровня ISPmanager

- Авторизация, роли, аудит и 2FA.
- Безопасные очереди задач и воркеры (реальный certbot/runbook).
- DNS-модуль и автоматическая запись A/MX/TXT.
- Полная почтовая безопасность (DKIM/SPF/DMARC, rspamd, clamav).
- Резервные копии, мониторинг, алерты, multi-tenant.

Если хочешь, следующим шагом могу сделать v2 с:
1) логином админа,
2) API-ключами,
3) фоновой очередью задач,
4) авто-выпуском certbot без ручного запуска.
