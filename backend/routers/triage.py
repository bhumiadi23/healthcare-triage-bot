"""
POST /triage — Compute urgency from extracted symptoms, save triage result
"""
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from datetime import datetime, timezone

router = APIRouter()


class TriageRequest(BaseModel):
    session_id: str
    symptoms: list[str]


# Rule-based triage map (Neo4j replaces this on Day 2)
SYMPTOM_URGENCY: dict[str, tuple[str, float, list[str]]] = {
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
}

URGENCY_SCORE   = {"CRITICAL": 92, "HIGH": 70, "MEDIUM": 40, "LOW": 15}
URGENCY_ACTION  = {
    "CRITICAL": "Call 911 immediately",
    "HIGH":     "Go to the ER now",
    "MEDIUM":   "Visit urgent care within 4 hours",
    "LOW":      "Schedule a GP appointment",
}
URGENCY_ORDER   = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]


def compute_triage(symptoms: list[str]) -> dict:
    max_urgency = "LOW"
    conditions: list[str] = []
    confidence_sum = 0.0
    matched = 0

    for s in symptoms:
        s_lower = s.lower()
        if s_lower in SYMPTOM_URGENCY:
            urgency, conf, conds = SYMPTOM_URGENCY[s_lower]
            if URGENCY_ORDER.index(urgency) > URGENCY_ORDER.index(max_urgency):
                max_urgency = urgency
            conditions.extend(c for c in conds if c not in conditions)
            confidence_sum += conf
            matched += 1

    confidence = round(confidence_sum / matched, 2) if matched else 0.5

    return {
        "urgency_level":      max_urgency,
        "urgency_score":      URGENCY_SCORE[max_urgency],
        "possible_conditions": conditions[:5],
        "recommended_action": URGENCY_ACTION[max_urgency],
        "confidence":         confidence,
    }


@router.post("")
async def triage(req: TriageRequest, request: Request):
    db = request.app.state.db

    session = await db.patient_sessions.find_one({"session_id": req.session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    result = compute_triage(req.symptoms)
    result["triaged_at"] = datetime.now(timezone.utc)

    await db.patient_sessions.update_one(
        {"session_id": req.session_id},
        {"$set": {"triage_result": result, "status": "completed"}},
    )

    return {"session_id": req.session_id, **result}
