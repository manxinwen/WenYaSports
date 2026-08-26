from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.db import database

app = FastAPI(title="FIT Multi-Agent Analysis API", version="0.1.0")

# Initialize the SQLite long-term memory database
database.init_db()

# CORS: allow all origins for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
def health():
    return {"status": "ok"}
