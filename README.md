# digit-catalog-analyzer

Сервис на FastAPI для скачивания каталога текстовых файлов через ограниченное API и расчета статистики по цифрам в содержимом файлов.

## Что реализовано

- Страница скачивания с кнопкой `Скачать данные`.
- Фоновая загрузка через Celery worker, веб-сервер не блокируется долгим процессом.
- Обход каталога до пустого ответа `/api/files/names`.
- Скачивание ZIP пачками максимум по 3 файла.
- Отметка `/api/files/downloaded` только после успешного сохранения файлов в БД.
- Корректная обработка `429` и `403` с паузой по `Retry-After`.
- Поддержка `X-Candidate-Id`.
- Прогресс процесса: старт по Новосибирску, получено имен, скачано файлов, текущий статус.
- Страница скачанных файлов: сортировка по времени, пагинация, выбор точечно, всей страницы или всех файлов.
- Расчет общей статистики по выбранным файлам и статистики по каждому файлу.
- Идемпотентное хранение файлов по уникальному имени.
- Предрасчет и кеширование статистики файла в PostgreSQL.
- Redis используется для быстрого чтения прогресса UI.
- Nginx проксирует приложение.
- Docker Compose поднимает FastAPI, PostgreSQL, Redis, RabbitMQ, Celery и Nginx.
- Тесты для подсчета статистики, чтения ZIP и обработки `Retry-After`.

## Быстрый запуск

Создайте `.env`, если хотите задать адрес API один раз для всего сервиса:

```bash
cp .env.example .env
```

Укажите адрес внешнего API:

```env
EXTERNAL_API_BASE_URL=https://example.com
CANDIDATE_ID=your-stable-id
```

Запустите сервис:

```bash
docker compose up --build
```

Откройте UI:

```text
http://localhost:8080
```

RabbitMQ management доступен по адресу:

```text
http://localhost:15672
```

Логин и пароль: `catalog` / `catalog`.

## Деплой на VPS

Самый простой способ получить публичную ссылку для тестового — развернуть весь стек на небольшом VPS с Docker и открыть порт `80`.

Подойдет сервер с 1-2 CPU и 1-2 GB RAM. Для долгого скачивания лучше 2 GB RAM.

На сервере установите Docker и Docker Compose plugin, затем склонируйте репозиторий:

```bash
git clone https://github.com/<your-username>/digit-catalog-analyzer.git
cd digit-catalog-analyzer
cp .env.production.example .env
```

В `.env` обязательно замените пароли и укажите внешний API:

```env
EXTERNAL_API_BASE_URL=https://example.com
CANDIDATE_ID=your-stable-candidate-id
POSTGRES_PASSWORD=strong-db-password
RABBITMQ_DEFAULT_PASS=strong-rabbit-password
DATABASE_URL=postgresql+psycopg://catalog:strong-db-password@db:5432/catalog
CELERY_BROKER_URL=amqp://catalog:strong-rabbit-password@rabbitmq:5672//
```

Запустите production compose:

```bash
docker compose -f docker-compose.prod.yml up --build -d
```

Проверка статуса:

```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f app worker
```

После запуска приложение будет доступно по IP сервера:

```text
http://<server-ip>
```

Если есть домен, создайте `A`-запись на IP сервера. После обновления DNS ссылка будет такой:

```text
http://your-domain.ru
```

Для HTTPS можно поставить внешний reverse proxy с TLS, например Caddy/Traefik на сервере или TLS termination у облачного провайдера. Внутри проекта оставлен Nginx, чтобы соответствовать стеку компании.

Остановка production-стека:

```bash
docker compose -f docker-compose.prod.yml down
```

Данные PostgreSQL и Redis лежат в Docker volumes и не удаляются обычным `down`.

## Страницы

- `/` — запуск скачивания и live-прогресс.
- `/files` — список файлов, выбор и расчеты.
- `/health` — healthcheck приложения.

## Архитектура

```text
Browser -> Nginx -> FastAPI -> PostgreSQL
                      |       -> Redis progress cache
                      |
                      -> RabbitMQ -> Celery worker -> External Files API
                                             |
                                             -> PostgreSQL
```

FastAPI отвечает за UI и JSON API. Celery worker выполняет долгую загрузку каталога, потому что внешний API намеренно ограничивает частоту запросов и может заставить ждать. PostgreSQL хранит скачанные файлы, время скачивания и статистику. Redis хранит свежий progress snapshot для polling-интерфейса.

## Важные детали реализации

- Если внешний API возвращает `429` или `403`, worker читает `Retry-After`, переводит процесс в статус `waiting`, ждет нужное время и повторяет запрос.
- Если `Retry-After` отсутствует, для `429` используется безопасная пауза 10 секунд, для `403` — 30 минут.
- Клиент внешнего API поддерживает два варианта тела запроса для `download` и `downloaded`: `{"names": [...]}` и `[...]`. Это сделано потому, что в задании не описан точный JSON-контракт тела POST-запросов.
- ZIP считается валидным только если содержит все запрошенные файлы. Иначе пачка не отмечается как скачанная, чтобы не потерять данные.
- Уникальный индекс по имени файла защищает от дублей при повторных попытках после сетевых ошибок.

## Локальная разработка без Docker

Нужны Python 3.12+, PostgreSQL, Redis и RabbitMQ.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

В отдельном терминале:

```bash
celery -A app.tasks.celery_app:celery_app worker --loglevel=INFO
```

## Тесты

```bash
pytest
```

В Docker:

```bash
docker compose exec app pytest
```
