"""FastAPI entrypoint.

Run:  uvicorn app.main:app --reload --port 8000
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import settings
from app import db


@asynccontextmanager
async def lifespan(_: FastAPI):
    await db.connect()          # create pool + ensure schema
    yield
    await db.disconnect()


app = FastAPI(title="Order Supervisor", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "llm_enabled": settings.llm_enabled}
