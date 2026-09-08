# Подключение Redis к job-tracker

Четыре файла кладутся рядом с остальным кодом приложения (`app/cache.py`,
`app/rate_limit.py`, `tests/test_cache.py`). Ниже — что дописать в существующее.

## 1. Зависимости

```
redis>=5.0
slowapi>=0.1.9
pytest-asyncio>=0.23
```

`redis.asyncio` входит в основной пакет `redis` начиная с 4.2 — отдельный
`aioredis` не нужен, он давно влит в основной клиент.

## 2. main.py

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app import cache
from app.rate_limit import limiter


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await cache.close_client()


app = FastAPI(lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

Дальше на конкретных ручках:

```python
@app.get("/jobs")
@limiter.limit("30/minute")
async def get_jobs(request: Request, status: str = "open"):
    return await list_jobs(status=status)
```

**Главная грабля slowapi:** параметр `request: Request` обязан быть в сигнатуре
явно. Без него декоратор не находит запрос и молча не срабатывает — лимита
просто не будет, и тест это поймает раньше, чем прод.

Инвалидация на записи:

```python
@app.post("/jobs")
@limiter.limit("10/minute")
async def create_job(request: Request, payload: JobIn):
    job = await repository.create(payload)
    await cache.invalidate("jobs:list")
    return job
```

## 3. docker-compose.yml

```yaml
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  api:
    depends_on:
      redis:
        condition: service_healthy
    environment:
      REDIS_URL: redis://redis:6379/0
      CACHE_TTL_SECONDS: "60"
```

`condition: service_healthy` важнее, чем кажется: без него `api` стартует
раньше, чем Redis начинает принимать соединения, и первые запросы падают в
fail-open ветку. В CI это выглядит как случайно мигающий тест.

## 4. GitHub Actions

```yaml
    services:
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 5s
          --health-timeout 3s
          --health-retries 5

    env:
      REDIS_URL: redis://localhost:6379/15
```

## 5. Абзац в README

> **Кэширование и рейт-лимитинг.** Тяжёлые выборки кэшируются в Redis с TTL и
> инвалидацией по префиксу на запись; инвалидация идёт через `SCAN`, а не
> `KEYS`, чтобы не блокировать сервер на большом keyspace. Кэш работает
> fail-open — при недоступности Redis приложение продолжает отвечать, теряя
> только скорость. Рейт-лимитер (slowapi) хранит счётчики там же, поэтому лимит
> общий для всех воркеров, а не умножается на их число. Ключ лимита —
> пользователь, если он аутентифицирован, иначе IP.

## Что проверить руками

1. `docker compose up -d redis`, потом `pytest tests/test_cache.py -v`
2. Дёрнуть `/jobs` 31 раз подряд — 31-й должен вернуть 429 с заголовком `Retry-After`
3. Остановить Redis на живом приложении и убедиться, что `/jobs` продолжает отвечать
