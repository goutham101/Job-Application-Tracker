from contextlib import asynccontextmanager

from fastapi import FastAPI

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
app.include_router(applications_router)
app.include_router(stats_router)
app.include_router(questions_router)
app.include_router(matches_router)
