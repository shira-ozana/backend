from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import auth, features, repositories, tasks, users

app = FastAPI(title=get_settings().app_name, version="0.1.0")

# להחליף ב-origin של הקליינט (למשל http://localhost:4200 ל-Angular)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router)
app.include_router(auth.router)
app.include_router(repositories.router)
app.include_router(features.router)
app.include_router(tasks.router)


# cd "$env:USERPROFILE\Desktop\sdlc"
# .venv\Scripts\activate
# cd backend
# python -m uvicorn app.main:app --reload
