# Multi-Currency Budgeting API

A FastAPI-based budgeting service with multi-currency accounting, JWT-based authentication, Celery background tasks, and PostgreSQL/Redis support.

## Overview

This project helps manage:

- users and authentication
- accounts and balances
- transactions with currency conversion
- budgets and category limits
- periodic exchange-rate refreshes from Frankfurter

## Stack

- Python 3.12+
- FastAPI
- SQLAlchemy + Alembic
- PostgreSQL
- Redis
- Celery + Celery Beat
- Docker Compose
- pytest

## Project structure

```text
.
├── apps/
│   ├── accounts/
│   ├── budgets/
│   ├── exchange/
│   ├── transactions/
│   └── users/
├── core/
│   ├── config/
│   ├── constants/
│   ├── db/
│   ├── security/
│   └── utils/
├── tests/
├── alembic/
├── scripts/
├── main.py
├── Dockerfile
├── docker-compose.dev.yml
├── docker-compose.test.yml
├── docker-compose.prod.yml
├── requirements.txt
├── requirements-dev.txt
├── README.md
├── .env.example
├── Makefile
├── alembic.ini
└── .gitignore
```

## Environment and Compose layout

The project uses separate Compose files in the repository root:

- [docker-compose.dev.yml](docker-compose.dev.yml) — local development with reload
- [docker-compose.test.yml](docker-compose.test.yml) — isolated testing environment
- [docker-compose.prod.yml](docker-compose.prod.yml) — production deployment

This keeps the setup explicit and avoids ambiguity when multiple environments exist. Use the file explicitly with `-f`.

## Prerequisites

- Docker and Docker Compose support (`docker compose` is the preferred form)
- Python 3.12+ for local non-Docker development
- GNU Make is optional and only needed for the shortcuts in the Makefile

> Database and Redis are provided automatically by Docker Compose in the dev/test stack. If you run locally without Docker, define `DATABASE_URL` and `REDIS_URL` in `.env`.

## Environment setup first

Before running the app, create a `.env` file from the example:

```bash
cp .env.example .env
```

Then adjust values for your current environment. This is required for app startup, especially in Docker and production settings.

## Quick start

### Development environment

```bash
docker compose -f docker-compose.dev.yml up -d
```

Access:

- API: http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- PostgreSQL: localhost:5432
- Redis: localhost:6379

Useful commands:

```bash
docker compose -f docker-compose.dev.yml logs -f api
docker compose -f docker-compose.dev.yml exec api alembic upgrade head
docker compose -f docker-compose.dev.yml exec api python -m scripts.seed_data
docker compose -f docker-compose.dev.yml down
```

### Testing environment

Most tests use the isolated SQLite fixtures from
[tests/conftest.py](tests/conftest.py). PostgreSQL concurrency tests use separate
connections and a fresh temporary schema per test, without modifying existing
application tables. The test database role must be able to create schemas.

For a quick project-level shortcut:

```bash
docker compose -f docker-compose.test.yml run --build --rm api python -m pytest -q
```

The test Compose environment sets `TEST_DATABASE_URL` automatically, so this
command includes PostgreSQL integration tests. To run only these tests:

```bash
make test-integration
# Or directly:
docker compose -f docker-compose.test.yml run --build --rm api python -m pytest -m postgres -q
```

These tests verify concurrent expenses, concurrent incomes, idempotency races,
and balance rollback on an insert failure. They check actual PostgreSQL lock
waits with separate sessions. Tables are created from SQLAlchemy metadata;
this suite does not validate Alembic migrations.

Run a specific file:

```bash
docker compose -f docker-compose.test.yml run --rm api python -m pytest tests/test_exchange_rates.py -q
docker compose -f docker-compose.test.yml run --rm api python -m pytest tests/test_transactions.py -q
docker compose -f docker-compose.test.yml run --rm api python -m pytest tests/test_budgets.py -q
```

The test Compose stack sets `TEST_POSTGRES_URL` and waits for PostgreSQL to be
ready, so its full test command includes the concurrency checks. To run just
those checks:

```bash
docker compose -f docker-compose.test.yml run --build --rm api python -m pytest tests/test_transactions_concurrency.py -q
```

For native runs, set `TEST_POSTGRES_URL` to a PostgreSQL test database. When it is
unset, the five concurrency cases are explicitly skipped. An unreachable or
invalid configured database fails the tests. These tests use PostgreSQL's default
`READ COMMITTED` isolation, force requests to overlap, and verify actual blocking
via `pg_blocking_pids`, HTTP responses, persisted balances and transaction counts.
They cover simultaneous expenses with sufficient/insufficient funds, a shared
key for the same request, and conflicting payloads on the same/different accounts.

### Production environment

Use the same `.env` file creation step first, then start the stack:

```bash
cp .env.example .env
# update values for production

docker compose -f docker-compose.prod.yml up -d
```

## Local development without Docker

```bash
python -m venv .venv
source .venv/Scripts/activate   # Windows
# or: source .venv/bin/activate # Linux/macOS

pip install -r requirements-dev.txt
alembic upgrade head
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Environment variables

Settings are loaded in this order:

1. OS environment variables
2. `.env`
3. defaults from [core/config/settings.py](core/config/settings.py)

Key variables:

```env
ENV=development
DEBUG=True
DATABASE_URL=postgresql://postgres:postgres@db:5432/mcb_dev
REDIS_URL=redis://redis:6379/0
SECRET_KEY=your-secret-key
ACCESS_TOKEN_EXPIRE_MINUTES=15
EXCHANGE_RATE_UPDATE_INTERVAL_MINUTES=60
```

Access tokens expire after 15 minutes by default. Logging out revokes all refresh
tokens for that user; already-issued access tokens remain valid only until their
short expiration.

## Database and migrations
Transaction `Idempotency-Key` values are unique per user across all their
accounts. Different users may reuse the same key. Repeating a request with the
same key and parameters returns the original transaction; changing parameters
returns HTTP 409. The API requires this header. Internal transactions without
a key (such as currency conversions) may coexist for the same user.

Apply migrations before starting updated application processes. The migration
backfills transaction owners from their accounts and replaces the global key
index with a unique `(user_id, idempotency_key)` constraint. Downgrading requires
keys to be globally unique again; if users have reused keys, the downgrade fails
without deleting transactions.

The project uses Alembic.

Create a migration:

```bash
alembic revision --autogenerate -m "Add new table"
```

Apply migrations:

```bash
alembic upgrade head
```

Check status/history:

```bash
alembic current
alembic history --verbose
```

Inside Docker:

```bash
docker compose -f docker-compose.dev.yml exec api alembic upgrade head
```

## Demo seed data

The project includes a safe seed script for local dev/test data only.

```bash
docker compose -f docker-compose.dev.yml exec api python -m scripts.seed_data
```

Behavior:

- it only works in `development` or `testing` environments
- it requires the local Compose database name (`mcb_dev` or `mcb_test`)
- it creates only missing demo records and does not overwrite existing matching data
- it refuses to run against production or non-local databases

Demo credentials:

- email: `demo@example.com`
- password: `dev-only-password`

## Budget spending

Budgets have their own currency (EUR by default). Spending is calculated from
expense transactions in the current period and converted from each account's
currency into the budget currency using the latest stored exchange rates. As
rates are refreshed, historical converted spending can change. Statistics totals
are converted to EUR.
Weekly budgets use Monday 00:00 UTC through the following Monday; monthly budgets
use the first day of the month through the first day of the next month. The end
boundary is exclusive.

For `GET /api/v1/budgets/statistics`, `total_spent` is the sum of unique expense
transactions covered by at least one of the user's budgets in its current
calendar period. A 25 EUR food expense covered by both weekly and monthly food
budgets contributes 25 EUR to `total_spent`, while each budget's `spent_amount`
is 25 EUR. Expenses outside all budget categories/windows are excluded; with no
budgets, `total_spent` is zero. At month boundaries the total includes the union
of the current weekly and monthly windows, which can include days in the prior
month. Each window includes its start and excludes its end.

Expenses are aggregated by their stored transaction currency and converted
directly to EUR using current stored rates. `total_limit` and `total_remaining`
sum limits and remaining allowances for each budget independently, and status
counts also refer to budgets. As a result, overlapping budgets can make
`total_remaining` differ from `total_limit - total_spent`.

## Exchange-rate integration

Rates are refreshed from the keyless Frankfurter API.

Important details:

- no API key is required
- the service uses EUR as the base currency
- the app stores derived pairs globally and reuses them for transaction conversion
- Celery Beat triggers one refresh at startup; if the periodic entry is already due, it uses
  that dispatch instead of sending a duplicate. Later refreshes follow
  `EXCHANGE_RATE_UPDATE_INTERVAL_MINUTES`.

Example request:

```text
GET https://api.frankfurter.dev/v2/rates?base=EUR&quotes=USD,GBP
```

The system then derives the remaining pairs from EUR-based rates, for example:

- USD -> GBP is calculated from EUR -> GBP and EUR -> USD
- all global pair rates are stored in the database

Conversions use cached rates; monetary requests do not call Frankfurter
synchronously. `EXCHANGE_RATE_MAX_AGE_HOURS` is a positive integer, defaulting to
48. A rate expires when the time since `updated_at` reaches that threshold.
Timestamps without timezone information are interpreted as UTC; a missing
timestamp is treated as expired. Existing old/undated rates need a successful
background refresh before they can be used again.

`updated_at` records the last successful provider refresh, including responses
whose values did not change. It is not the provider's quote date: a successful
weekend refresh can confirm the same quote. The refresher validates all required
quotes before writing any pairs. Failed requests, missing quotes, non-finite or
non-positive rates leave cached values and freshness timestamps unchanged.

When a calculation needs an unavailable rate, the API returns HTTP 503 with a
structured `detail` object containing `code`, `message`, `from_currency`,
`to_currency` and `updated_at`:

- `exchange_rate_unavailable`: the required pair is absent;
- `exchange_rate_stale`: the pair exists but its refresh time is expired/unknown.

Financial operations that fail this check leave balances unchanged and create
no transaction. Budget checks can also require a rate even when the transaction
and account currencies match. Statistics return 503 if a required conversion
cannot be completed, rather than skipping expenses or returning a partial total.
Amounts that need no conversion work without exchange rates. Completed requests
replayed with the same idempotency key return the original transaction even if
its rate subsequently expires or disappears. Changing a zero-balance account's
currency does not require a monetary conversion or a rate.

The read-only exchange-rate endpoints still expose expired records for
inspection; requesting an absent rate resource by ID returns 404. These response
contracts are described in OpenAPI. The policy uses the existing `updated_at`
column and needs no database migration.

Supported currencies:

- EUR
- USD
- GBP

## Authentication and security

The app uses JWT-based authentication with a bearer token flow. Passwords are hashed before storage.

Primary auth endpoints are exposed via FastAPI docs and the application login flow.

## Tests

Tests live under [tests](tests). Pytest automatically loads [tests/conftest.py](tests/conftest.py),
which provides an isolated in-memory database and FastAPI dependency overrides.
PostgreSQL fixtures live in `tests/integration/conftest.py`. Use the test
commands in the Testing environment section above.

## Useful commands

### Container status

```bash
docker compose -f docker-compose.dev.yml ps
```

### Database access

```bash
docker compose -f docker-compose.dev.yml exec db psql -U postgres -d mcb_dev
```

### Redis access

```bash
docker compose -f docker-compose.dev.yml exec redis redis-cli
```

### Rebuild image after dependency changes

```bash
docker compose -f docker-compose.dev.yml build --no-cache
```

### Drop local DB and restart services

```bash
docker compose -f docker-compose.dev.yml down -v
docker compose -f docker-compose.dev.yml up --build
```

## Troubleshooting

### Port already in use

```bash
# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Linux/macOS
lsof -i :8000
kill -9 <PID>
```

### Database connection issues

```bash
docker compose -f docker-compose.dev.yml ps
docker compose -f docker-compose.dev.yml logs db
```

### Exchange-rate issues

```bash
docker compose -f docker-compose.dev.yml logs worker
docker compose -f docker-compose.dev.yml logs beat
```

### Missing dependencies or build issues

```bash
docker compose -f docker-compose.dev.yml build --no-cache
```

## Notes

- the app is designed around explicit environment separation between dev, test, and prod
- the test environment is isolated from production data by design
- Celery workers and Beat are part of the normal runtime flow and should be started with the matching Compose file
- optional Makefile shortcuts are listed by `make help`
