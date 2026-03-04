from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from services.supabase_client import get_supabase
from routes.resumes import router as resumes_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: verify Supabase connection
    get_supabase()
    print("✓ Supabase client initialised")
    yield
    # Shutdown: nothing to clean up for now
    print("⏻ Shutting down")


settings = get_settings()

app = FastAPI(
    title=settings.APP_TITLE,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # tighten for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(resumes_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": settings.APP_VERSION}
