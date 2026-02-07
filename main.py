from fastapi import FastAPI
from db import engine, Base

from routers.health import router as health_router
from routers.oauth import router as oauth_router
from routers.settings import router as settings_router
from routers.webhooks import router as webhooks_router

app = FastAPI()

Base.metadata.create_all(bind=engine)

app.include_router(health_router)
app.include_router(oauth_router)
app.include_router(settings_router)
app.include_router(webhooks_router)