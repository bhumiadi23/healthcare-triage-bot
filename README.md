# 🏥 Healthcare Symptom Checker & Triage Bot

> AI-powered pre-triage system to reduce ER overcrowding by routing patients to the right level of care.

## The Problem
40–60% of ER visits are non-emergencies. This bot pre-triages patients using BioBERT + a Neo4j Knowledge Graph so critical patients aren't buried in queues.

## Stack
| Layer | Tech |
|-------|------|
| Frontend | React 18 + TailwindCSS |
| Backend | FastAPI (Python 3.11) |
| NLP | BioBERT (HuggingFace) |
| Knowledge Graph | Neo4j 5 |
| Database | MongoDB 7 |
| Maps | Google Maps API |

## Quick Start
```bash
cp .env.example .env          # Add your GOOGLE_MAPS_API_KEY
docker-compose up --build
```
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000/docs
- Neo4j Browser: http://localhost:7474

## Seed the Knowledge Graph
```bash
cd knowledge-graph
pip install neo4j
python seed_graph.py
```

## Project Docs
- [Project Document](docs/PROJECT_DOCUMENT.md)
- [Architecture Flowchart](docs/ARCHITECTURE_FLOWCHART.md)

## MVP Scope
Neo4j is seeded with the **top 50 most common presenting symptoms** only — ensuring 100% accurate triage rules before expansion.

## Triage Levels
| Level | Action |
|-------|--------|
| 🔴 CRITICAL | Call 911 immediately |
| 🟠 HIGH | Go to ER now |
| 🟡 MEDIUM | Urgent care within 4 hours |
| 🟢 LOW | Schedule GP appointment |
