from fastapi import APIRouter

from app.api import (
    admin,
    calendar,
    characters,
    collection,
    discord,
    friends,
    games,
    groups,
    health,
    me,
    meetups,
    notifications,
    play_log,
    rpg_systems,
    votes,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(me.router)
api_router.include_router(games.router)
api_router.include_router(collection.router)
api_router.include_router(friends.router)
api_router.include_router(groups.router)
api_router.include_router(meetups.router)
api_router.include_router(calendar.router)
api_router.include_router(votes.router)
api_router.include_router(play_log.router)
api_router.include_router(rpg_systems.router)
api_router.include_router(characters.router)
api_router.include_router(notifications.router)
api_router.include_router(admin.router)
api_router.include_router(discord.router)
