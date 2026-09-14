from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import admin, auth, messages, pets, walkers, walks, payments


app = FastAPI(
    title="Woofy Go API",
    version="0.1.0",
    description="Backend de Woffy Go - paseo de perros en tiempo real",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(pets.router)
app.include_router(walkers.router)
app.include_router(walks.router)
app.include_router(messages.router)
app.include_router(payments.router)
app.include_router(admin.router)


@app.get("/health", tags=["health"])
def health() -> dict:
    return {"status": "ok", "service": "woffygo-api"}
