from fastapi import APIRouter

from app.api import health, me

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(me.router)
