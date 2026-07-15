import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.applications import router as applications_router
from app.db import pool
from app.matches import router as matches_router
from app.questions import router as questions_router
from app.stats import router as stats_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool.open()
    yield
    pool.close()


app = FastAPI(title="Job Application Tracker", lifespan=lifespan)

# Frontend and API deploy as separate Render services (different origins).
# Single-user app with no auth/cookies, so a permissive default is low-risk;
# set FRONTEND_ORIGIN to lock it down once the frontend URL is known.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.environ["FRONTEND_ORIGIN"]] if "FRONTEND_ORIGIN" in os.environ else ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(applications_router)
app.include_router(stats_router)
app.include_router(questions_router)
app.include_router(matches_router)
