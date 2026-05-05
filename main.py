from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.config.settings import settings

# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="A comprehensive API for managing multi-currency budgets",
    version="0.1.0",
    debug=settings.debug
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_credentials,
    allow_methods=settings.cors_methods,
    allow_headers=settings.cors_headers,
)

# Health check endpoint
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "environment": settings.env,
        "app": settings.app_name
    }

# Welcome endpoint
@app.get("/")
async def root():
    return {
        "message": "Welcome to Multi-Currency Budgeting API",
        "docs": "/docs",
        "redoc": "/redoc",
        "openapi_schema": "/openapi.json"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        workers=settings.workers if not settings.debug else 1
    )


@app.get("/items/{item_id}")
def read_item(item_id: int, q: str | None = None):
    return {"item_id": item_id, "q": q}
