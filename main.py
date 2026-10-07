from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.accounts.routes import router as accounts_router
from apps.budgets.routes import router as budgets_router
from apps.exchange.routes import router as exchange_rates_router
from apps.transactions.routes import router as transactions_router
from apps.users.routes import router as auth_router
from core.config.settings import settings

app = FastAPI(
    title=settings.app_name,
    description="A comprehensive API for managing multi-currency budgets",
    version="0.1.0",
    debug=settings.debug,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_credentials,
    allow_methods=settings.cors_methods,
    allow_headers=settings.cors_headers,
)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(accounts_router, prefix="/api/v1")
app.include_router(transactions_router, prefix="/api/v1")
app.include_router(exchange_rates_router, prefix="/api/v1")
app.include_router(budgets_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "environment": settings.env,
        "app": settings.app_name,
    }


@app.get("/")
async def root():
    return {
        "message": "Welcome to Multi-Currency Budgeting API",
        "docs": "/docs",
        "redoc": "/redoc",
        "openapi_schema": "/openapi.json",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        workers=settings.workers if not settings.debug else 1,
    )
