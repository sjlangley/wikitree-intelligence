"""Entrypoint for the API application."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from api.enums import Environment
from api.routes import auth, health, user
from api.settings import settings

logger = logging.getLogger(__name__)


app = FastAPI()

# Configure CORS
if settings.client_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.client_origins,
        allow_credentials=False,
        allow_methods=['GET', 'POST'],
        allow_headers=['Content-Type', 'Authorization'],
    )

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret_key,
    session_cookie='wikitree-intelligence-session',
    max_age=60 * 60 * 24 * 7,  # 7 days
    same_site='lax',
    https_only=settings.environment
    in (Environment.PRODUCTION, Environment.STAGING),
)

app.include_router(auth.router, prefix='/auth')
app.include_router(health.router, prefix='/health')
app.include_router(user.router, prefix='/user')
