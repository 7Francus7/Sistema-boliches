from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import Base, engine
from .routers import analytics, auth, bootstrap, sync
from .seed import run_seed


@asynccontextmanager
async def lifespan(app: FastAPI):
    # MVP: create_all en vez de Alembic. Cambiar a migraciones antes de prod.
    Base.metadata.create_all(bind=engine)
    run_seed()
    yield


app = FastAPI(
    title="Boliches SaaS API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(bootstrap.router)
app.include_router(sync.router)
app.include_router(analytics.router)
