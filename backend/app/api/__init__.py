from fastapi import APIRouter

from app.api import collection, friends, games, groups, health, me, meetups

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(me.router)
api_router.include_router(games.router)
api_router.include_router(collection.router)
api_router.include_router(friends.router)
api_router.include_router(groups.router)
api_router.include_router(meetups.router)
