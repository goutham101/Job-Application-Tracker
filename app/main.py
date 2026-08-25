import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.applications import router as applications_router
from app.auth import verify_api_key
from app.db import pool
from app.matches import router as matches_router
from app.questions import router as questions_router
from app.stats import router as stats_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool.open()
    yield
    pool.close()


app = FastAPI(
    title="Job Application Tracker",
    lifespan=lifespan,
    dependencies=[Depends(verify_api_key)],
)

# Frontend and API deploy as separate Render services (different origins).
# Set FRONTEND_ORIGIN to lock CORS down once the frontend URL is known; set
# API_KEY (see app/auth.py) before deploying anywhere public — without it
# every route above is reachable by anyone with the URL.
frontend_origin = os.environ.get("FRONTEND_ORIGIN")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_origin] if frontend_origin else ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


app.include_router(applications_router)
app.include_router(stats_router)
app.include_router(questions_router)
app.include_router(matches_router)
