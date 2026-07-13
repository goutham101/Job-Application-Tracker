from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db import pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool.open()
    yield
    pool.close()


app = FastAPI(title="Job Application Tracker", lifespan=lifespan)
