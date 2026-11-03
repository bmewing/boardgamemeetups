from fastapi import APIRouter

from app.api import collection, games, health, me

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(me.router)
api_router.include_router(games.router)
api_router.include_router(collection.router)
