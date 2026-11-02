import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import Base, engine, SessionLocal
from app.api.v1.api import api_router
from app.services.category_service import CategoryService

# Setup structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("eventdhara.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure tables exist and seed canonical taxonomy
    logger.info("Initializing database schemas...")
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database schemas created/verified successfully.")
    except Exception as e:
        logger.error("Error creating database tables: %s", e)

    db = SessionLocal()
    try:
        category_service = CategoryService(db)
        category_service.seed_initial_categories()
        logger.info("Canonical category hierarchy verified.")
    except Exception as e:
        logger.error("Error seeding initial categories: %s", e)
    finally:
        db.close()

    yield

    logger.info("Shutting down EventDhara AI Platform backend.")


app = FastAPI(
    title=settings.APP_NAME,
    description="Enterprise AI Data Operations Platform for Event Decoration Photograph Management",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permits local development on any port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve stored processed/approved images as static files
storage_path = os.path.abspath(settings.STORAGE_ROOT)
os.makedirs(storage_path, exist_ok=True)
app.mount("/storage", StaticFiles(directory=storage_path), name="storage")

# Include API Router
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "environment": settings.ENVIRONMENT,
        "database": "connected"
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled Exception on %s: %s", request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal enterprise service error occurred. Please consult system logs."}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
