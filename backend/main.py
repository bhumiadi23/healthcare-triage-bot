"""
FastAPI App Entry Point — Healthcare Triage Bot
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import connect_db, close_db
from neo4j_db import connect_neo4j, close_neo4j
from routers import chat, triage, report, history, graph


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db = await connect_db()
    try:
        app.state.neo4j = await connect_neo4j()
    except Exception as e:
        print(f"[Neo4j] Warning: could not connect — {e}")
        app.state.neo4j = None
    from ner import load_biobert
    load_biobert()
    yield
    await close_db()
    await close_neo4j()


app = FastAPI(
    title="Healthcare Triage Bot API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router,    prefix="/chat",    tags=["Chat"])
app.include_router(triage.router,  prefix="/triage",  tags=["Triage"])
app.include_router(report.router,  prefix="/report",  tags=["Report"])
app.include_router(history.router, prefix="/history", tags=["History"])
app.include_router(graph.router,   prefix="/graph",   tags=["Knowledge Graph"])


@app.get("/health")
async def health():
    return {"status": "ok"}
