"""HRM-Core FastAPI Application Entry Point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.core.database import init_db
from app.shared.routers import auth, health, users
from app.recruiting.routers import jobs, candidates, applications, pipeline, tasks
from app.admin.routers import config as admin_config


settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    await init_db()
    yield
    # Shutdown
    pass


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Unified HR Platform - Recruiting & Compensation Management",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": settings.app_version}


# API routers
app.include_router(
    auth.router,
    prefix=f"{settings.api_v1_prefix}/auth",
    tags=["Authentication"],
)

app.include_router(
    users.router,
    prefix=f"{settings.api_v1_prefix}/users",
    tags=["Users"],
)

# Recruiting module
app.include_router(
    jobs.router,
    prefix=f"{settings.api_v1_prefix}/recruiting/jobs",
    tags=["Recruiting - Jobs"],
)

app.include_router(
    candidates.router,
    prefix=f"{settings.api_v1_prefix}/recruiting/candidates",
    tags=["Recruiting - Candidates"],
)

app.include_router(
    applications.router,
    prefix=f"{settings.api_v1_prefix}/recruiting/applications",
    tags=["Recruiting - Applications"],
)

app.include_router(
    pipeline.router,
    prefix=f"{settings.api_v1_prefix}/recruiting/pipeline",
    tags=["Recruiting - Pipeline"],
)

app.include_router(
    tasks.router,
    prefix=f"{settings.api_v1_prefix}/recruiting/tasks",
    tags=["Recruiting - Tasks"],
)

# Admin module
app.include_router(
    admin_config.router,
    prefix=f"{settings.api_v1_prefix}/admin",
    tags=["Admin - Configuration"],
)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
    )
