"""
GET  /graph/symptom/{name}     — diseases linked to a symptom from Neo4j
POST /graph/query              — multi-symptom graph triage query
GET  /graph/demo/chest-pain    — live demo: chest pain node connections + risk factors
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from neo4j_db import get_neo4j

router = APIRouter()


@router.get("/symptom/{symptom_name}")
async def get_diseases_by_symptom(symptom_name: str):
    """Query Neo4j: which diseases does this symptom indicate?"""
    driver = get_neo4j()
    async with driver.session() as session:
        result = await session.run("""
            MATCH (s:Symptom)-[r:INDICATES]->(d:Disease)-[:HAS_URGENCY]->(u:UrgencyLevel)
            WHERE toLower(s.name) = toLower($symptom)
            RETURN d.name AS disease,
                   u.level AS urgency,
                   u.action AS recommended_action,
                   r.weight AS confidence
            ORDER BY r.weight DESC
        """, symptom=symptom_name)

        records = await result.data()

    if not records:
        raise HTTPException(status_code=404, detail=f"No diseases found for symptom: '{symptom_name}'")

    return {
        "symptom":  symptom_name,
        "diseases": records,
    }


class GraphTriageRequest(BaseModel):
    symptoms: list[str]


@router.post("/query")
async def graph_triage_query(req: GraphTriageRequest):
    """Multi-symptom Neo4j query — returns ranked diseases + urgency."""
    driver = get_neo4j()
    async with driver.session() as session:
        result = await session.run("""
            MATCH (s:Symptom)-[r:INDICATES]->(d:Disease)-[:HAS_URGENCY]->(u:UrgencyLevel)
            WHERE toLower(s.name) IN $symptoms
            WITH d, u, SUM(r.weight) AS match_score, COLLECT(s.name) AS matched_symptoms
            ORDER BY match_score DESC
            RETURN d.name          AS disease,
                   u.level         AS urgency,
                   u.score         AS urgency_score,
                   u.action        AS recommended_action,
                   match_score,
                   matched_symptoms
            LIMIT 5
        """, symptoms=[s.lower() for s in req.symptoms])

        records = await result.data()

    if not records:
        raise HTTPException(status_code=404, detail="No matching diseases found in graph.")

    top = records[0]
    return {
        "symptoms_queried": req.symptoms,
        "top_diagnosis":    top["disease"],
        "urgency_level":    top["urgency"],
        "urgency_score":    top["urgency_score"],
        "recommended_action": top["recommended_action"],
        "differential":     records,
    }


@router.get("/demo/chest-pain")
async def demo_chest_pain():
    """
    Live demo query — shows full node connections for 'chest pain':
    Symptom → Diseases → UrgencyLevels + RiskFactors
    """
    driver = get_neo4j()
    async with driver.session() as session:

        # Diseases linked to chest pain
        diseases_result = await session.run("""
            MATCH (s:Symptom {name: 'chest pain'})-[r:INDICATES]->(d:Disease)-[:HAS_URGENCY]->(u:UrgencyLevel)
            RETURN d.name AS disease, u.level AS urgency, r.weight AS confidence
            ORDER BY r.weight DESC
        """)
        diseases = await diseases_result.data()

        # Risk factors for those diseases
        risk_result = await session.run("""
            MATCH (s:Symptom {name: 'chest pain'})-[:INDICATES]->(d:Disease)-[:HAS_RISK_FACTOR]->(rf:RiskFactor)
            RETURN d.name AS disease, rf.name AS risk_factor, rf.type AS type
            ORDER BY d.name
        """)
        risk_factors = await risk_result.data()

        # Co-occurring diseases
        co_result = await session.run("""
            MATCH (s:Symptom {name: 'chest pain'})-[:INDICATES]->(d:Disease)-[:CO_OCCURS_WITH]->(d2:Disease)
            RETURN d.name AS disease, d2.name AS co_occurs_with
        """)
        co_occurs = await co_result.data()

    return {
        "demo":        "Chest Pain — Full Node Connections",
        "symptom":     "chest pain",
        "diseases":    diseases,
        "risk_factors": risk_factors,
        "co_occurrences": co_occurs,
        "graph_summary": {
            "total_diseases":     len(diseases),
            "total_risk_factors": len(risk_factors),
            "total_co_occurrences": len(co_occurs),
        },
    }
