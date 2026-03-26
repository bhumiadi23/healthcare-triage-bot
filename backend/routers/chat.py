"""
POST /chat              — Full pipeline: NER -> Neo4j triage -> Handoff Report (single call)
GET  /chat/{session_id} — Get session conversation turns
PUT  /chat/{session_id} — Update patient info
"""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from neo4j_db import get_neo4j

router = APIRouter()

# ── Symptom → (urgency, confidence, conditions) fallback if Neo4j is down ────
SYMPTOM_URGENCY = {
    "chest pain":             ("CRITICAL", 0.92, ["Myocardial Infarction", "Angina"]),
    "vomiting blood":         ("CRITICAL", 0.95, ["GI Bleed"]),
    "sudden severe headache": ("CRITICAL", 0.95, ["Subarachnoid Hemorrhage", "Meningitis"]),
    "facial drooping":        ("CRITICAL", 0.98, ["Stroke"]),
    "arm weakness":           ("CRITICAL", 0.95, ["Stroke"]),
    "slurred speech":         ("CRITICAL", 0.95, ["Stroke"]),
    "syncope":                ("CRITICAL", 0.90, ["Cardiac Arrhythmia"]),
    "severe abdominal pain":  ("CRITICAL", 0.90, ["Ruptured Aortic Aneurysm"]),
    "difficulty swallowing":  ("CRITICAL", 0.90, ["Epiglottitis"]),
    "rash":                   ("CRITICAL", 0.88, ["Meningococcemia"]),
    "shortness of breath":    ("HIGH",     0.85, ["Pulmonary Embolism", "Asthma Attack"]),
    "sweating":               ("HIGH",     0.80, ["Hypoglycemia"]),
    "high fever":             ("HIGH",     0.82, ["Sepsis", "Meningitis"]),
    "confusion":              ("HIGH",     0.80, ["Sepsis", "Stroke"]),
    "palpitations":           ("HIGH",     0.85, ["Atrial Fibrillation"]),
    "abdominal pain":         ("HIGH",     0.80, ["Appendicitis"]),
    "swollen leg":            ("HIGH",     0.85, ["Deep Vein Thrombosis"]),
    "back pain":              ("HIGH",     0.75, ["Kidney Stone"]),
    "eye pain":               ("HIGH",     0.85, ["Acute Angle-Closure Glaucoma"]),
    "black stool":            ("HIGH",     0.90, ["GI Bleed"]),
    "dizziness":              ("MEDIUM",   0.75, ["Vertigo", "Hypoglycemia"]),
    "headache":               ("MEDIUM",   0.70, ["Migraine", "Tension Headache"]),
    "fever":                  ("MEDIUM",   0.65, ["UTI", "Influenza"]),
    "nausea":                 ("MEDIUM",   0.65, ["Gastroenteritis"]),
    "cough":                  ("MEDIUM",   0.65, ["Pneumonia", "COVID-19"]),
    "sore throat":            ("MEDIUM",   0.72, ["Strep Throat", "Tonsillitis"]),
    "body aches":             ("MEDIUM",   0.68, ["Influenza"]),
    "runny nose":             ("LOW",      0.85, ["Common Cold", "Allergic Rhinitis"]),
}

URGENCY_SCORE  = {"CRITICAL": 92, "HIGH": 70, "MEDIUM": 40, "LOW": 15}
URGENCY_ACTION = {
    "CRITICAL": "Call 108 immediately",
    "HIGH":     "Go to the ER now",
    "MEDIUM":   "Visit urgent care within 4 hours",
    "LOW":      "Schedule a GP appointment",
}
URGENCY_ORDER = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

SYMPTOM_KEYWORDS = list(SYMPTOM_URGENCY.keys())


# ── Helpers ───────────────────────────────────────────────────────────────────

def mock_ner(text: str) -> list[dict]:
    text_lower = text.lower()
    return [
        {"text": kw, "label": "SYMPTOM", "confidence": 0.90}
        for kw in SYMPTOM_KEYWORDS if kw in text_lower
    ]


def rule_triage(symptoms: list[str]) -> dict:
    max_urgency = "LOW"
    conditions: list[str] = []
    conf_sum, matched = 0.0, 0
    for s in symptoms:
        entry = SYMPTOM_URGENCY.get(s.lower())
        if entry:
            urgency, conf, conds = entry
            if URGENCY_ORDER.index(urgency) > URGENCY_ORDER.index(max_urgency):
                max_urgency = urgency
            conditions.extend(c for c in conds if c not in conditions)
            conf_sum += conf
            matched += 1
    return {
        "urgency_level":       max_urgency,
        "urgency_score":       URGENCY_SCORE[max_urgency],
        "possible_conditions": conditions[:5],
        "recommended_action":  URGENCY_ACTION[max_urgency],
        "confidence":          round(conf_sum / matched, 2) if matched else 0.5,
        "source":              "rule_engine",
    }


async def neo4j_triage(symptoms: list[str]) -> dict | None:
    """Query Neo4j for triage. Returns None if Neo4j is unavailable."""
    driver = get_neo4j()
    if not driver:
        return None
    try:
        async with driver.session() as s:
            result = await s.run("""
                MATCH (sym:Symptom)-[r:INDICATES]->(d:Disease)-[:HAS_URGENCY]->(u:UrgencyLevel)
                WHERE toLower(sym.name) IN $symptoms
                WITH d, u, SUM(r.weight) AS score, COLLECT(sym.name) AS matched
                ORDER BY score DESC
                RETURN d.name AS disease, u.level AS urgency,
                       u.score AS urgency_score, u.action AS recommended_action,
                       score AS match_score, matched
                LIMIT 5
            """, symptoms=[s.lower() for s in symptoms])
            records = await result.data()

        if not records:
            return None

        top = records[0]
        return {
            "urgency_level":       top["urgency"],
            "urgency_score":       top["urgency_score"],
            "possible_conditions": [r["disease"] for r in records],
            "recommended_action":  top["recommended_action"],
            "confidence":          round(top["match_score"] / len(symptoms), 2),
            "source":              "neo4j",
            "differential":        records,
        }
    except Exception:
        return None


def build_report(session_id: str, patient_info: dict,
                 user_input: str, entities: list[dict],
                 triage: dict) -> dict:
    return {
        "report_id":    str(uuid.uuid4()),
        "session_id":   session_id,
        "generated_at": datetime.now(timezone.utc),
        "patient_summary": patient_info,
        "chief_complaint": user_input,
        "extracted_symptoms": [
            {"symptom": e["text"], "severity": None, "duration": None}
            for e in entities
        ],
        "differential_diagnosis": [
            {
                "condition":   c,
                "probability": round(triage["confidence"] * 0.9 ** i, 2),
                "icd10_code":  None,
            }
            for i, c in enumerate(triage.get("possible_conditions", []))
        ],
        "triage_decision": {
            "urgency_level":      triage["urgency_level"],
            "recommended_action": triage["recommended_action"],
            "assigned_at":        datetime.now(timezone.utc),
        },
        "vital_flags":  ["Requires immediate physician review"]
                        if triage["urgency_level"] == "CRITICAL" else [],
        "doctor_notes":   None,
        "report_pdf_url": None,
    }


# ── Request / Response models ─────────────────────────────────────────────────

class ChatRequest(BaseModel):
    session_id: str | None = None
    user_input: str
    patient_info: dict = {}


class UpdatePatientRequest(BaseModel):
    age: int | None = None
    sex: str | None = None
    known_conditions: list[str] = []


# ── POST /chat — full pipeline in one call ────────────────────────────────────

@router.post("", summary="Full pipeline: NER -> Neo4j triage -> Handoff Report")
async def post_chat(req: ChatRequest, request: Request):
    db         = request.app.state.db
    session_id = req.session_id or str(uuid.uuid4())
    now        = datetime.now(timezone.utc)

    # Step 1 — NER: extract symptoms
    entities = mock_ner(req.user_input)
    symptoms = [e["text"] for e in entities]

    # Step 2 — Triage: Neo4j first, fallback to rule engine
    triage = await neo4j_triage(symptoms) or rule_triage(symptoms)
    triage["triaged_at"] = now
    triage["overridden"] = False

    # Step 3 — Build handoff report
    report = build_report(session_id, req.patient_info, req.user_input, entities, triage)

    # Step 4 — Persist session + report to MongoDB
    turn = {
        "user_input":         req.user_input,
        "extracted_entities": entities,
        "timestamp":          now,
    }

    await db.patient_sessions.update_one(
        {"session_id": session_id},
        {
            "$setOnInsert": {
                "session_id":   session_id,
                "created_at":   now,
                "patient_info": req.patient_info,
                "status":       "completed",
            },
            "$set":  {"triage_result": triage},
            "$push": {"conversation": turn},
        },
        upsert=True,
    )
    await db.handoff_reports.insert_one({**report})
    report.pop("_id", None)

    # Step 5 — Return everything in one response
    return {
        "session_id":         session_id,
        "extracted_entities": entities,
        "symptoms_found":     symptoms,
        "triage": {
            "urgency_level":       triage["urgency_level"],
            "urgency_score":       triage["urgency_score"],
            "recommended_action":  triage["recommended_action"],
            "possible_conditions": triage["possible_conditions"],
            "confidence":          triage["confidence"],
            "source":              triage.get("source"),
        },
        "report": report,
    }


# ── GET /chat/{session_id} ────────────────────────────────────────────────────

@router.get("/{session_id}", summary="Get session conversation + triage result")
async def get_chat(session_id: str, request: Request):
    db = request.app.state.db
    session = await db.patient_sessions.find_one({"session_id": session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session.pop("_id", None)
    return session


# ── PUT /chat/{session_id} ────────────────────────────────────────────────────

@router.put("/{session_id}", summary="Update patient info on a session")
async def update_patient_info(session_id: str, req: UpdatePatientRequest, request: Request):
    db = request.app.state.db
    session = await db.patient_sessions.find_one({"session_id": session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    updates = {k: v for k, v in req.model_dump().items() if v is not None and v != []}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    await db.patient_sessions.update_one(
        {"session_id": session_id},
        {"$set": {f"patient_info.{k}": v for k, v in updates.items()}},
    )
    return {"session_id": session_id, "updated": updates, "message": "Patient info updated."}
