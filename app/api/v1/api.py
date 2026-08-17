from fastapi import APIRouter
from app.api.v1.endpoints.hello import router as hello_router
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.users import router as users_router
from app.api.v1.endpoints.audio import router as audio_router
from app.api.v1.endpoints.vocabulary import router as vocabulary_router
from app.api.v1.endpoints.reading import router as reading_router
from app.api.v1.endpoints.gym import router as gym_router
from app.api.v1.endpoints.todo import router as todo_router

api_router = APIRouter()
api_router.include_router(hello_router, prefix="/v1/hello", tags=["hello"])
api_router.include_router(auth_router, prefix="/v1/auth", tags=["auth"])
api_router.include_router(users_router, prefix="/v1/users", tags=["users"])
api_router.include_router(audio_router, prefix="/v1/audio", tags=["audio"])
api_router.include_router(vocabulary_router, prefix="/v1/vocabulary", tags=["vocabulary"])
api_router.include_router(reading_router, prefix="/v1/reading", tags=["reading"])
api_router.include_router(gym_router, prefix="/v1/gym", tags=["gym"])
api_router.include_router(todo_router, prefix="/v1/todo", tags=["todo"])






