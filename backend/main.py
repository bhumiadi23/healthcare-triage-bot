"""
FastAPI App Entry Point — Healthcare Triage Bot
"""
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.openapi.docs import get_swagger_ui_html
from database import connect_db, close_db
from routers import chat, triage, report, history, graph, hospitals


async def _connect_neo4j_safe(app: FastAPI):
    try:
        from neo4j_db import connect_neo4j
        app.state.neo4j = await connect_neo4j()
    except Exception as e:
        print(f"[Neo4j] Warning: could not connect - {e}")
        app.state.neo4j = None


async def _close_neo4j_safe():
    try:
        from neo4j_db import close_neo4j
        await close_neo4j()
    except Exception:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db = await connect_db()
    await _connect_neo4j_safe(app)
    yield
    await close_db()
    await _close_neo4j_safe()


app = FastAPI(
    title="Healthcare Triage Bot API",
    description="""
AI-powered symptom checker & triage system.

## Flow
**POST /chat** → extract symptoms → **POST /triage** → urgency score → **POST /report** → Doctor Handoff Report

## Urgency Levels
| Level | Action |
|-------|--------|
| CRITICAL | Call 911 immediately |
| HIGH | Go to ER now |
| MEDIUM | Urgent care within 4h |
| LOW | Schedule GP appointment |
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router,      prefix="/chat",      tags=["Chat"])
app.include_router(triage.router,    prefix="/triage",    tags=["Triage"])
app.include_router(report.router,    prefix="/report",    tags=["Report"])
app.include_router(history.router,   prefix="/history",   tags=["History"])
app.include_router(graph.router,     prefix="/graph",     tags=["Knowledge Graph"])
app.include_router(hospitals.router, prefix="/hospitals", tags=["Hospitals"])


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/docs", include_in_schema=False)
async def custom_swagger():
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="Healthcare Triage Bot - API Docs",
        swagger_ui_parameters={
            "defaultModelsExpandDepth": -1,
            "docExpansion": "list",
            "filter": True,
            "syntaxHighlight.theme": "monokai",
            "tryItOutEnabled": True,
        },
    )


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def landing():
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Healthcare Triage Bot API</title>
  <style>
    *{margin:0;padding:0;box-sizing:border-box}
    body{font-family:'Segoe UI',sans-serif;background:#0f172a;color:#e2e8f0;
         min-height:100vh;display:flex;flex-direction:column;align-items:center;
         justify-content:center;padding:2rem}
    .badge{background:#ef4444;color:#fff;font-size:.75rem;font-weight:700;
           padding:.25rem .75rem;border-radius:999px;letter-spacing:.1em;
           margin-bottom:1.5rem;text-transform:uppercase}
    h1{font-size:2.5rem;font-weight:800;background:linear-gradient(90deg,#38bdf8,#818cf8);
       -webkit-background-clip:text;-webkit-text-fill-color:transparent;
       margin-bottom:.75rem;text-align:center}
    p.sub{color:#94a3b8;font-size:1rem;margin-bottom:2.5rem;text-align:center;max-width:480px}
    .cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));
           gap:1rem;width:100%;max-width:860px;margin-bottom:2.5rem}
    .card{background:#1e293b;border:1px solid #334155;border-radius:12px;
          padding:1.25rem 1.5rem;transition:border-color .2s}
    .card:hover{border-color:#38bdf8}
    .method{font-size:.7rem;font-weight:700;letter-spacing:.08em;padding:.2rem .5rem;
            border-radius:4px;margin-bottom:.5rem;display:inline-block}
    .post{background:#166534;color:#86efac}
    .get{background:#1e3a5f;color:#7dd3fc}
    .route{font-size:.95rem;font-weight:600;color:#e2e8f0;margin-bottom:.3rem}
    .desc{font-size:.8rem;color:#64748b}
    .urgency-bar{display:flex;gap:.5rem;margin-bottom:2.5rem;flex-wrap:wrap;justify-content:center}
    .ub{padding:.4rem 1rem;border-radius:999px;font-size:.8rem;font-weight:700}
    .critical{background:#fef2f2;color:#dc2626}
    .high{background:#fff7ed;color:#ea580c}
    .medium{background:#fefce8;color:#ca8a04}
    .low{background:#f0fdf4;color:#16a34a}
    .actions{display:flex;gap:1rem;flex-wrap:wrap;justify-content:center}
    a.btn{padding:.65rem 1.5rem;border-radius:8px;font-weight:600;font-size:.9rem;
          text-decoration:none;transition:opacity .2s}
    a.btn:hover{opacity:.85}
    .btn-primary{background:#38bdf8;color:#0f172a}
    .btn-secondary{background:#1e293b;color:#e2e8f0;border:1px solid #334155}
    .status{margin-top:2rem;font-size:.8rem;color:#475569}
    .dot{display:inline-block;width:8px;height:8px;border-radius:50%;
         background:#22c55e;margin-right:6px;animation:pulse 1.5s infinite}
    @keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
  </style>
</head>
<body>
  <div class="badge">Healthcare AI</div>
  <h1>Triage Bot API</h1>
  <p class="sub">AI-powered symptom checker that routes patients to the right level of care using BioBERT + Neo4j Knowledge Graph.</p>
  <div class="urgency-bar">
    <span class="ub critical">CRITICAL &mdash; Call 108</span>
    <span class="ub high">HIGH &mdash; Go to ER</span>
    <span class="ub medium">MEDIUM &mdash; Urgent Care</span>
    <span class="ub low">LOW &mdash; See GP</span>
  </div>
  <div class="cards">
    <div class="card">
      <span class="method post">POST</span>
      <div class="route">/chat</div>
      <div class="desc">Submit symptoms, extract entities via BioBERT NER</div>
    </div>
    <div class="card">
      <span class="method post">POST</span>
      <div class="route">/triage</div>
      <div class="desc">Compute urgency level from extracted symptoms</div>
    </div>
    <div class="card">
      <span class="method get">GET</span>
      <div class="route">/graph/symptom/{name}</div>
      <div class="desc">Query Neo4j &mdash; diseases linked to a symptom</div>
    </div>
    <div class="card">
      <span class="method get">GET</span>
      <div class="route">/graph/demo/chest-pain</div>
      <div class="desc">Live demo &mdash; chest pain node connections + risk factors</div>
    </div>
    <div class="card">
      <span class="method post">POST</span>
      <div class="route">/report</div>
      <div class="desc">Generate Doctor Handoff Report</div>
    </div>
    <div class="card">
      <span class="method get">GET</span>
      <div class="route">/history/{session_id}</div>
      <div class="desc">Retrieve full patient session history</div>
    </div>
  </div>
  <div class="actions">
    <a class="btn btn-primary" href="/docs">Swagger UI</a>
    <a class="btn btn-secondary" href="/redoc">ReDoc</a>
    <a class="btn btn-secondary" href="/health">Health Check</a>
    <a class="btn btn-secondary" href="/graph/demo/chest-pain">Live Demo</a>
  </div>
  <p class="status"><span class="dot"></span>API is running &mdash; v1.0.0</p>
</body>
</html>"""
