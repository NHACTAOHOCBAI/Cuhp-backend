from fastapi import APIRouter
from app.api.v1.endpoints.hello import router as hello_router
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.users import router as users_router

api_router = APIRouter()
api_router.include_router(hello_router, prefix="/v1/hello", tags=["hello"])
api_router.include_router(auth_router, prefix="/v1/auth", tags=["auth"])
api_router.include_router(users_router, prefix="/v1/users", tags=["users"])




