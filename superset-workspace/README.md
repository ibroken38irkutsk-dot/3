# Рабочая область Superset

Своя локальная копия Superset на вашем компьютере: Superset 6.1 + PostgreSQL в Docker.
При первом запуске сама подключает базу «Аналитика», загружает «Бюджет ДДУС» из Excel
и собирает дашборд.

## Установка (один раз)

1. **Docker Desktop.** Скачать с https://www.docker.com/products/docker-desktop/ и установить
   (нужны права администратора; на корпоративном ноутбуке, возможно, через ИТ).
   После установки запустить Docker Desktop и дождаться статуса «Engine running».
2. **Распаковать архив** в папку без пробелов и кириллицы, например `C:\superset`.
   Внутри должны быть папки `superset-workspace` и `ddus`.
3. **Положить Excel** с листом «Бюджет ДДУС» в `C:\superset\superset-workspace\data\`.
4. **Запустить.** Открыть PowerShell и выполнить:
   ```
   cd C:\superset\superset-workspace
   docker compose up -d --build
   ```
   Первый раз скачивается ~1 ГБ и всё настраивается — 5–10 минут.
   Ход загрузки: `docker compose logs -f superset`, ждать строку
   `>> Superset готов: http://localhost:8088`.
5. **Открыть** http://localhost:8088, логин `admin`, пароль `admin`.
   Дашборд: Dashboards → «Бюджет ДДУС». Язык интерфейса — флажок справа вверху.

## Каждый день

| Что нужно | Команда (в папке `superset-workspace`) |
|---|---|
| Запустить | `docker compose up -d` |
| Остановить | `docker compose stop` |
| Обновить данные ДДУС (новый Excel положили в `data`) | `docker compose restart superset` |
| Посмотреть логи | `docker compose logs -f superset` |
| Удалить всё вместе с данными | `docker compose down -v` |

Дашборды, графики и данные сохраняются между перезапусками и перезагрузками ПК.

## Свои данные через интерфейс

Загрузить любой Excel/CSV как таблицу:
1. Settings → Database Connections → «Аналитика» → Edit → Advanced → Security →
   включить «Allow file uploads to database» → Finish.
2. Datasets → «+» (или меню «+» справа вверху) → Upload file → выбрать файл,
   база «Аналитика», схема `public`.
3. Из датасета строить графики: Charts → «+».

## Подключиться к базе извне (DBeaver, Excel, Python)

Хост `localhost`, порт `5433`, база `analytics`, пользователь `bi`, пароль `bi`.

## Безопасность

Это локальный стенд для работы на своём ПК. Перед тем как открывать его другим людям,
поменяйте пароли: задайте `ADMIN_PASSWORD` и `SUPERSET_SECRET_KEY` в файле `.env`
рядом с `docker-compose.yml` (пароль `admin` поменяется только на чистой установке).
