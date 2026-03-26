"""
GET  /graph/symptoms              — List all symptom nodes
GET  /graph/symptom/{name}        — Diseases linked to a symptom
POST /graph/query                 — Multi-symptom triage query
PUT  /graph/disease/{name}/risk   — Add a risk factor to a disease
GET  /graph/demo/chest-pain       — Live KPI demo
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from neo4j_db import get_neo4j

router = APIRouter()


def _driver():
    d = get_neo4j()
    if d is None:
        raise HTTPException(status_code=503, detail="Graph database unavailable")
    return d


# GET — list all symptom nodes
@router.get("/symptoms", summary="List all symptom nodes in the graph")
async def list_symptoms():
    async with _driver().session() as s:
        result = await s.run("""
            MATCH (sym:Symptom)-[:INDICATES]->(d:Disease)-[:HAS_URGENCY]->(u:UrgencyLevel)
            WITH sym, COLLECT(DISTINCT d.name) AS diseases, MAX(u.score) AS max_score
            RETURN sym.name AS symptom, diseases, max_score
            ORDER BY max_score DESC
        """)
        records = await result.data()
    return {"total": len(records), "symptoms": records}


# GET — diseases by symptom
@router.get("/symptom/{symptom_name}", summary="Get diseases linked to a symptom")
async def get_diseases_by_symptom(symptom_name: str):
    async with _driver().session() as s:
        result = await s.run("""
            MATCH (sym:Symptom)-[r:INDICATES]->(d:Disease)-[:HAS_URGENCY]->(u:UrgencyLevel)
            WHERE toLower(sym.name) = toLower($symptom)
            OPTIONAL MATCH (d)-[:HAS_RISK_FACTOR]->(rf:RiskFactor)
            RETURN d.name AS disease,
                   u.level AS urgency,
                   u.action AS recommended_action,
                   r.weight AS confidence,
                   COLLECT(rf.name) AS risk_factors
            ORDER BY r.weight DESC
        """, symptom=symptom_name)
        records = await result.data()

    if not records:
        raise HTTPException(status_code=404, detail=f"No diseases found for symptom: '{symptom_name}'")
    return {"symptom": symptom_name, "total_diseases": len(records), "diseases": records}


# POST — multi-symptom graph triage
class GraphTriageRequest(BaseModel):
    symptoms: list[str]


@router.post("/query", summary="Multi-symptom Neo4j triage query")
async def graph_triage_query(req: GraphTriageRequest):
    async with _driver().session() as s:
        result = await s.run("""
            MATCH (sym:Symptom)-[r:INDICATES]->(d:Disease)-[:HAS_URGENCY]->(u:UrgencyLevel)
            WHERE toLower(sym.name) IN $symptoms
            WITH d, u, SUM(r.weight) AS match_score, COLLECT(sym.name) AS matched_symptoms
            ORDER BY match_score DESC
            RETURN d.name            AS disease,
                   u.level           AS urgency,
                   u.score           AS urgency_score,
                   u.action          AS recommended_action,
                   match_score,
                   matched_symptoms
            LIMIT 5
        """, symptoms=[s.lower() for s in req.symptoms])
        records = await result.data()

    if not records:
        raise HTTPException(status_code=404, detail="No matching diseases found in graph.")

    top = records[0]
    return {
        "symptoms_queried":   req.symptoms,
        "top_diagnosis":      top["disease"],
        "urgency_level":      top["urgency"],
        "urgency_score":      top["urgency_score"],
        "recommended_action": top["recommended_action"],
        "differential":       records,
    }


# PUT — add risk factor to a disease
class RiskFactorRequest(BaseModel):
    risk_factor: str
    type: str  # age | comorbidity | lifestyle


@router.put("/disease/{disease_name}/risk", summary="Add a risk factor to a disease node")
async def add_risk_factor(disease_name: str, req: RiskFactorRequest):
    async with _driver().session() as s:
        result = await s.run("""
            MATCH (d:Disease {name: $disease})
            MERGE (rf:RiskFactor {name: $risk})
              SET rf.type = $type
            MERGE (d)-[:HAS_RISK_FACTOR]->(rf)
            RETURN d.name AS disease, rf.name AS risk_factor
        """, disease=disease_name, risk=req.risk_factor, type=req.type)
        record = await result.single()

    if not record:
        raise HTTPException(status_code=404, detail=f"Disease '{disease_name}' not found in graph")

    return {
        "disease":     record["disease"],
        "risk_factor": record["risk_factor"],
        "type":        req.type,
        "message":     "Risk factor added to graph.",
    }


# GET — live KPI demo: chest pain full connections
@router.get("/demo/chest-pain", summary="Live demo: chest pain node connections + risk factors")
async def demo_chest_pain():
    async with _driver().session() as s:
        diseases = await (await s.run("""
            MATCH (sym:Symptom {name: 'chest pain'})-[r:INDICATES]->(d:Disease)-[:HAS_URGENCY]->(u:UrgencyLevel)
            RETURN d.name AS disease, u.level AS urgency, r.weight AS confidence
            ORDER BY r.weight DESC
        """)).data()

        risk_factors = await (await s.run("""
            MATCH (sym:Symptom {name: 'chest pain'})-[:INDICATES]->(d:Disease)-[:HAS_RISK_FACTOR]->(rf:RiskFactor)
            RETURN d.name AS disease, rf.name AS risk_factor, rf.type AS type
            ORDER BY d.name
        """)).data()

        co_occurs = await (await s.run("""
            MATCH (sym:Symptom {name: 'chest pain'})-[:INDICATES]->(d:Disease)-[:CO_OCCURS_WITH]->(d2:Disease)
            RETURN d.name AS disease, d2.name AS co_occurs_with
        """)).data()

    return {
        "demo":           "Chest Pain - Full Node Connections",
        "symptom":        "chest pain",
        "diseases":       diseases,
        "risk_factors":   risk_factors,
        "co_occurrences": co_occurs,
        "graph_summary": {
            "total_diseases":       len(diseases),
            "total_risk_factors":   len(risk_factors),
            "total_co_occurrences": len(co_occurs),
        },
    }
