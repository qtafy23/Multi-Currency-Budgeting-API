# Multi-Currency Budgeting API

## Quick Start with Docker

No need to install Python, PostgreSQL, or Redis locally! Everything runs in containers.

### Prerequisites
- Docker
- Docker Compose

### Development Environment (with hot-reload)

```bash
# Start all services
docker-compose -f docker-compose.dev.yml up -d

# Apply pending database migrations
docker-compose -f docker-compose.dev.yml exec api alembic upgrade head

# Add repeatable demo data to the development database
docker-compose -f docker-compose.dev.yml exec api python -m scripts.seed_data

# View logs
docker-compose -f docker-compose.dev.yml logs -f api

# Stop services
docker-compose -f docker-compose.dev.yml down
```

**Access:**
- API: http://localhost:8000
- Docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- PostgreSQL: localhost:5432
- Redis: localhost:6379

### Testing Environment

`pytest` automatically discovers and loads `tests/conftest.py` for every test run. The shared
fixtures defined there (`db_session` and `client`) are used by the API tests to create a fresh
in-memory SQLite database per test and override the application database dependency, so the tests
cannot read or modify dev/production data.

```bash
# Run tests with coverage
docker-compose -f docker-compose.test.yml up

# View coverage report
# Check htmlcov/index.html after tests complete
```

If you want to run a single test file directly in the Docker test container:

```bash
docker-compose -f docker-compose.test.yml run --rm api python -m pytest tests/test_auth_and_account_ownership.py -q
```

To add demo records to the test database manually, apply migrations first and then run:

```bash
docker-compose -f docker-compose.test.yml run --rm api alembic upgrade head
docker-compose -f docker-compose.test.yml run --rm api python -m scripts.seed_data
```

The seed is additive and repeatable: existing matching demo records are left unchanged.
It refuses to run unless `ENV` and the database name match the development or testing
Compose database. Demo login: `demo@example.test` / `dev-only-password`.

### Production Environment

```bash
# Create .env file with production values
cp .env.example .env
# Edit .env with your production settings

# Start services
docker-compose -f docker-compose.prod.yml up -d
```

## Configuration

### Environment Variables

Settings are loaded from (in priority order):
1. Environment variables
2. `.env` file
3. Default values in `core/config/settings.py`

### Available Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `ENV` | `development` | Environment: development, testing, production |
| `DEBUG` | `True` | Enable debug mode |
| `DATABASE_URL` | PostgreSQL dev | Database connection string |
| `REDIS_URL` | localhost:6379 | Redis connection string |
| `SECRET_KEY` | dev key | JWT secret (change in production!) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 30 | Token expiration time |
| `EXCHANGE_RATE_UPDATE_INTERVAL_MINUTES` | 1440 | Interval for periodic exchange rate updates (Celery Beat) |

### Example .env File

```env
ENV=development
DEBUG=True
DATABASE_URL=postgresql://postgres:postgres@db:5432/mcb_dev
REDIS_URL=redis://redis:6379/0
SECRET_KEY=your-secret-key
EXCHANGE_RATE_UPDATE_INTERVAL_MINUTES=60
```

## Exchange Rate Integration

### Overview

Exchange rates are fetched periodically from the keyless **Frankfurter API** at `https://api.frankfurter.dev/v2/rates` and stored globally for all users. EUR is the base currency; one request retrieves EUR-to-GBP and EUR-to-USD rates, and the remaining directions are derived from those values.

**Supported Currencies:**
- GBP (British Pound)
- USD (US Dollar)
- EUR (Euro)

### Setup

No API key is required. Set `EXCHANGE_RATE_UPDATE_INTERVAL_MINUTES` to configure how often Celery Beat refreshes rates.

### How It Works

1. **Celery Beat Scheduler**: Runs periodic task based on `EXCHANGE_RATE_UPDATE_INTERVAL_MINUTES`
2. **Exchange Rate Task**: Fetches EUR-based rates from Frankfurter API
3. **Database Update**: Creates or updates exchange rate records
4. **Global Access**: All users see identical, system-managed rates

### Frankfurter API Response Format

The API returns exchange rates in this format:

```json
[
  {"date": "2026-09-30", "base": "EUR", "quote": "GBP", "rate": 0.85659},
  {"date": "2026-09-30", "base": "EUR", "quote": "USD", "rate": 1.1354}
]
```

The request is `GET https://api.frankfurter.dev/v2/rates?base=EUR&quotes=gbp,usd`. For example, `USD -> GBP` is calculated as `(EUR -> GBP) / (EUR -> USD)`.

### Exchange Rate Pairs

The system maintains the following exchange rate pairs:

- GBP → USD
- GBP → EUR
- USD → GBP
- USD → EUR
- EUR → GBP
- EUR → USD

All pairs are automatically created and updated on each refresh cycle.

### Architecture Notes

- **System-Managed**: Exchange rates are read-only to users
- **API Endpoints**: GET /api/v1/exchange-rates/ (list), GET /api/v1/exchange-rates/{id} (retrieve)
- **No Manual Changes**: Users cannot create, update, or delete exchange rates
- **Automatic Refresh**: Celery Beat periodically syncs rates
- **Transaction Conversion**: Transactions in different currencies use global rates

### Troubleshooting

**Exchange rates not updating:**
- Verify Redis is running: `docker-compose logs redis`
- Check Celery Beat logs: `docker-compose logs beat`
- Check worker logs: `docker-compose logs worker`
- Confirm API connectivity to `api.frankfurter.dev` from the application container

**Missing currency pairs:**
- Ensure database has at least one exchange rate record
- Check worker logs for Frankfurter request or response parsing errors
- Verify supported currencies are GBP, USD, EUR only

**API Errors:**
- Check the Frankfurter endpoint and query parameters in worker debug logs



### API Service
- FastAPI with Uvicorn
- Auto-reload on code changes (dev only)
- Multiple workers (prod only)

### Database Service
- PostgreSQL 16
- Persistent volumes for data
- Separate databases per environment (mcb_dev, mcb_test, mcb_prod)

### Redis Service
- Redis 7
- Cache layer
- Session storage

## Local Development (Without Docker)

If you prefer local development:

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements-dev.txt

# Run migrations (if applicable)
alembic upgrade head

# Start API
uvicorn main:app --reload
```

## Database Migrations

The project uses standard Alembic commands for database schema evolution.

### Standard Workflow

1. Generate a migration after model changes:

```bash
alembic revision --autogenerate -m "Add new table"
```

2. Review and edit the generated migration file in `alembic/versions/`.

3. Apply the migration:

```bash
alembic upgrade head
```

4. Inspect status and history:

```bash
alembic current
alembic history --verbose
```

### Docker Workflow

```bash
docker-compose -f docker-compose.dev.yml exec api alembic upgrade head
```

### Adding New Models

When you create new models:

1. Add them to your app's `models/` directory.
2. Import them in `apps/__init__.py`.
3. Generate a migration with Alembic:

```bash
alembic revision --autogenerate -m "Add new model"
```

4. Review and edit the generated migration file in `alembic/versions/`.
5. Apply the migration:

```bash
alembic upgrade head
```

Example:
```python
# apps/your_app/models/new_model.py
from sqlalchemy import Column, Integer, String
from core.db import Base

class NewModel(Base):
    __tablename__ = "new_models"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
```

```python
# apps/__init__.py
from .users.models import users
from .your_app.models import new_model  # Add this line
```

## Useful Commands

### View container status
```bash
docker-compose -f docker-compose.dev.yml ps
```

### Access database inside container
```bash
docker-compose -f docker-compose.dev.yml exec db psql -U postgres -d mcb_dev
```

### Access Redis CLI
```bash
docker-compose -f docker-compose.dev.yml exec redis redis-cli
```

### Rebuild image after dependency changes
```bash
docker-compose -f docker-compose.dev.yml build --no-cache
```

### Run a command inside container
```bash
docker-compose -f docker-compose.dev.yml exec api python -m pytest
```

## Troubleshooting

### Port already in use
```bash
# On Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# On Linux/Mac
lsof -i :8000
kill -9 <PID>
```

### Database connection errors
- Ensure all services are running: `docker-compose -f docker-compose.dev.yml ps`
- Check logs: `docker-compose -f docker-compose.dev.yml logs db`

### Rebuild everything from scratch
```bash
docker-compose -f docker-compose.dev.yml down -v
docker-compose -f docker-compose.dev.yml up --build
```

## Architecture

```
Multi-Currency Budgeting API
├── apps/              # Feature modules
│   ├── users/
│   ├── accounts/
│   ├── transactions/
│   ├── budgets/
│   ├── exchange/
│   ├── analytics/
│   └── audit/
├── core/              # Core utilities
│   ├── config/        # Settings management
│   ├── db/            # Database setup
│   ├── security/      # Auth & security
│   └── utils/         # Utilities
├── api/v1/            # API routes
├── services/          # Business logic
├── workers/           # Background jobs
└── main.py            # Entry point
```
