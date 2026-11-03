from fastapi import APIRouter

from app.api import games, health, me

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(me.router)
api_router.include_router(games.router)
