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

```bash
# Run tests with coverage
docker-compose -f docker-compose.test.yml up

# View coverage report
# Check htmlcov/index.html after tests complete
```

### Production Environment

```bash
# Create .env file with production values
cp .env.example .env
# Edit .env with your production settings

# Start services
docker-compose -f docker-compose.prod.yml up -d

# View logs
docker-compose -f docker-compose.prod.yml logs -f api
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

### Example .env File

```env
ENV=development
DEBUG=True
DATABASE_URL=postgresql://postgres:postgres@db:5432/mcb_dev
REDIS_URL=redis://redis:6379/0
SECRET_KEY=your-secret-key
```

## Service Details

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

### Auto-Migration System

The project includes an automated migration system that detects model changes and generates migration scripts automatically.

#### Quick Migration Commands

```bash
# Full auto-migration (generate + apply)
make migrate
# or
python scripts/migrate.py

# Dry run - see what would be migrated
make migrate-dry
# or
python scripts/migrate.py --dry-run

# Generate migration only (don't apply)
make migrate-generate
# or
python scripts/migrate.py --generate-only

# Check migration status
make db-status
```

#### Manual Migration (Advanced)

```bash
# Generate migration manually
alembic revision --autogenerate -m "Add new table"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1

# View history
alembic history
```

#### How Auto-Migration Works

1. **Model Registration**: All models are imported in `apps/__init__.py`
2. **Change Detection**: Alembic compares current models with database schema
3. **Script Generation**: Creates migration scripts automatically
4. **Safe Application**: Applies migrations with rollback capability

#### Adding New Models

When you create new models:

1. Add them to your app's `models/` directory
2. Import them in `apps/__init__.py`
3. Run `make migrate` to generate and apply migrations

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

### Manual Migration Commands

```bash
# Inside container
docker-compose -f docker-compose.dev.yml exec api alembic upgrade head

# Or locally
alembic upgrade head
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
