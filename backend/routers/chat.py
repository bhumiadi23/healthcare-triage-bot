"""
POST /chat              — Full pipeline: NER → Red-Flag → Neo4j → LLM Follow-up → Final Triage
GET  /chat/{session_id} — Get session conversation turns
PUT  /chat/{session_id} — Update patient info

Day 4 Pipeline:
  Chat input
    → BioBERT NER (extract symptoms)
    → Rule-Based Red-Flag Classifier (instant CRITICAL if triggered)
    → Neo4j Graph Query (differential diagnosis + match scores)
    → LLM Discriminating Question (narrow candidates, max 15 turns)
    → Updated Neo4j-backed session state
    → Final Urgency Classification + Handoff Report
"""
import uuid
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from neo4j_db import get_neo4j
from ner import extract_symptoms
from llm_engine import generate_discriminating_question, build_safe_diagnosis, generate_clarification_prompt
from rule_engine import check_red_flags
from conversation import (
    get_next_question,
    get_clarification_prompt,
    build_safe_response,
    should_finalize,
    MAX_QUESTIONS,
)

router = APIRouter()
log = logging.getLogger("CHAT")

# ── Urgency constants ─────────────────────────────────────────────────────────
URGENCY_SCORE  = {"CRITICAL": 92, "HIGH": 70, "MEDIUM": 40, "LOW": 15}
URGENCY_ACTION = {
    "CRITICAL": "Call 108 immediately",
    "HIGH":     "Go to the ER now",
    "MEDIUM":   "Visit urgent care within 4 hours",
    "LOW":      "Schedule a GP appointment",
}
URGENCY_ORDER = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

# ── Fallback symptom map (used when Neo4j is unavailable) ─────────────────────
SYMPTOM_URGENCY: dict[str, tuple[str, float, list[str]]] = {
    "chest pain":             ("CRITICAL", 0.92, ["Myocardial Infarction", "Angina"]),
    "vomiting blood":         ("CRITICAL", 0.95, ["Upper GI Bleed"]),
    "coughing up blood":      ("CRITICAL", 0.94, ["Pulmonary Embolism", "Tuberculosis"]),
    "sudden severe headache": ("CRITICAL", 0.95, ["Subarachnoid Hemorrhage", "Meningitis"]),
    "facial drooping":        ("CRITICAL", 0.98, ["Stroke"]),
    "arm weakness":           ("CRITICAL", 0.95, ["Stroke", "TIA"]),
    "slurred speech":         ("CRITICAL", 0.95, ["Stroke", "TIA"]),
    "syncope":                ("CRITICAL", 0.90, ["Cardiac Arrhythmia"]),
    "severe abdominal pain":  ("CRITICAL", 0.90, ["Ruptured Aortic Aneurysm"]),
    "difficulty swallowing":  ("CRITICAL", 0.90, ["Epiglottitis"]),
    "black stool":            ("CRITICAL", 0.92, ["Upper GI Bleed"]),
    "shortness of breath":    ("HIGH",     0.85, ["Pulmonary Embolism", "Asthma Attack"]),
    "sweating":               ("HIGH",     0.80, ["Hypoglycemia", "Myocardial Infarction"]),
    "high fever":             ("HIGH",     0.82, ["Sepsis", "Meningitis"]),
    "confusion":              ("HIGH",     0.80, ["Sepsis", "Stroke"]),
    "palpitations":           ("HIGH",     0.85, ["Atrial Fibrillation"]),
    "abdominal pain":         ("HIGH",     0.80, ["Appendicitis"]),
    "swollen leg":            ("HIGH",     0.85, ["Deep Vein Thrombosis"]),
    "back pain":              ("HIGH",     0.75, ["Kidney Stone"]),
    "eye pain":               ("HIGH",     0.85, ["Acute Angle-Closure Glaucoma"]),
    "neck stiffness":         ("HIGH",     0.85, ["Meningitis"]),
    "rash":                   ("HIGH",     0.80, ["Meningococcemia"]),
    "dizziness":              ("MEDIUM",   0.75, ["Vertigo", "Hypoglycemia"]),
    "headache":               ("MEDIUM",   0.70, ["Migraine", "Tension Headache"]),
    "fever":                  ("MEDIUM",   0.65, ["UTI", "Influenza"]),
    "nausea":                 ("MEDIUM",   0.65, ["Gastroenteritis"]),
    "cough":                  ("MEDIUM",   0.65, ["Pneumonia", "COVID-19"]),
    "sore throat":            ("MEDIUM",   0.72, ["Strep Throat", "Tonsillitis"]),
    "body aches":             ("MEDIUM",   0.68, ["Influenza"]),
    "fatigue":                ("MEDIUM",   0.60, ["Influenza", "Anaemia"]),
    "runny nose":             ("LOW",      0.85, ["Common Cold", "Allergic Rhinitis"]),
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _rule_triage(symptoms: list[str]) -> dict:
    """Fallback rule triage when Neo4j is unavailable."""
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
        "source":              "rule_fallback",
    }


async def _neo4j_triage(symptoms: list[str]) -> dict | None:
    """
    Query Neo4j for differential diagnosis.
    Returns None gracefully if Neo4j is unavailable — no crash.
    """
    driver = get_neo4j()
    if not driver:
        return None
    try:
        async with driver.session() as s:
            result = await s.run(
                """
                MATCH (sym:Symptom)-[r:INDICATES]->(d:Disease)-[:HAS_URGENCY]->(u:UrgencyLevel)
                WHERE toLower(sym.name) IN $symptoms
                WITH d, u, SUM(r.weight) AS score, COLLECT(sym.name) AS matched
                ORDER BY score DESC
                RETURN d.name AS disease, u.level AS urgency,
                       u.score AS urgency_score, u.action AS recommended_action,
                       score AS match_score, matched
                LIMIT 5
                """,
                symptoms=[s.lower() for s in symptoms],
            )
            records = await result.data()

        if not records:
            return None

        top = records[0]
        return {
            "urgency_level":       top["urgency"],
            "urgency_score":       top["urgency_score"],
            "possible_conditions": [r["disease"] for r in records],
            "recommended_action":  top["recommended_action"],
            "confidence":          round(top["match_score"] / max(len(symptoms), 1), 2),
            "source":              "neo4j",
            "differential":        records,
        }
    except Exception as e:
        log.warning(f"Neo4j triage query failed (non-fatal): {e}")
        return None


async def _update_neo4j_session_node(session_id: str, symptoms: list[str], urgency: str):
    """
    Write the updated symptom set and urgency back to Neo4j as a Session node.
    This satisfies the 'Updated Neo4j Graph' step in the pipeline.
    Non-fatal if Neo4j is unavailable.
    """
    driver = get_neo4j()
    if not driver:
        return
    try:
        async with driver.session() as s:
            await s.run(
                """
                MERGE (sess:Session {session_id: $sid})
                SET sess.symptoms = $symptoms,
                    sess.urgency  = $urgency,
                    sess.updated_at = datetime()
                """,
                sid=session_id,
                symptoms=symptoms,
                urgency=urgency,
            )
        log.info(f"Neo4j Session node updated: {session_id} → {urgency}")
    except Exception as e:
        log.warning(f"Neo4j session node update failed (non-fatal): {e}")


def _build_handoff_report(
    session_id: str,
    patient_info: dict,
    user_input: str,
    entities: list[dict],
    triage: dict,
) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "report_id":    str(uuid.uuid4()),
        "session_id":   session_id,
        "generated_at": now,
        "patient_summary": patient_info,
        "chief_complaint": user_input,
        "extracted_symptoms": [
            {"symptom": e["text"], "severity": None, "duration": None}
            for e in entities
        ],
        "differential_diagnosis": [
            {
                "condition":   c,
                "probability": round(triage["confidence"] * (0.9 ** i), 2),
                "icd10_code":  None,
            }
            for i, c in enumerate(triage.get("possible_conditions", []))
        ],
        "triage_decision": {
            "urgency_level":      triage["urgency_level"],
            "recommended_action": triage["recommended_action"],
            "assigned_at":        now,
        },
        "vital_flags": ["Requires immediate physician review"]
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


# ── POST /chat — Full Day 4 Pipeline ─────────────────────────────────────────

@router.post("", summary="Guided pipeline: NER → Red-Flag → Neo4j → LLM Follow-up → Final Triage")
async def post_chat(req: ChatRequest, request: Request):
    db         = request.app.state.db
    session_id = req.session_id or str(uuid.uuid4())
    now        = datetime.now(timezone.utc)

    # ── Step 1: Load session state ────────────────────────────────────────────
    session            = await db.patient_sessions.find_one({"session_id": session_id}) or {}
    collected_symptoms = set(session.get("collected_symptoms", []))
    turn_count         = int(session.get("turn_count", 0))
    asked_questions    = list(session.get("asked_questions", []))
    asked_clarifications = list(session.get("asked_clarifications", []))

    # ── Step 2: BioBERT NER — extract symptoms ────────────────────────────────
    try:
        ner_result   = extract_symptoms(req.user_input)
        new_symptoms = ner_result.get("neo4j_nodes", [])
        entities     = ner_result.get("entities", [])
    except Exception as e:
        log.error(f"NER extraction failed: {e}")
        new_symptoms, entities = [], []

    collected_symptoms.update(new_symptoms)
    log.info(f"[{session_id}] Turn {turn_count} | symptoms={collected_symptoms}")

    # ── Step 3: Safety net — gibberish / no symptoms detected ─────────────────
    if not collected_symptoms:
        clarification = get_clarification_prompt(asked_clarifications)
        asked_clarifications.append(clarification)

        await db.patient_sessions.update_one(
            {"session_id": session_id},
            {
                "$setOnInsert": {"session_id": session_id, "created_at": now, "patient_info": req.patient_info},
                "$set":  {"turn_count": turn_count + 1, "asked_clarifications": asked_clarifications, "status": "active"},
                "$push": {"conversation": {"user_input": req.user_input, "bot_reply": clarification, "timestamp": now}},
            },
            upsert=True,
        )
        return {
            "session_id":         session_id,
            "reply":              clarification,
            "extracted_entities": entities,
            "neo4j_nodes":        [],
            "triage":             None,
            "turn":               turn_count + 1,
        }

    # ── Step 4: Rule-Based Red-Flag Classifier ────────────────────────────────
    triage = check_red_flags(collected_symptoms)
    top_conditions: list[str] = []

    if triage:
        # Red flag fired — finalize immediately, no further questions
        is_final       = True
        top_conditions = triage.get("possible_conditions", [])
        log.info(f"[{session_id}] Red flag triggered: {triage['urgency_level']}")
    else:
        # ── Step 5: Neo4j Graph Query — differential diagnosis ────────────────
        triage = await _neo4j_triage(list(collected_symptoms))

        if triage is None:
            # Neo4j unavailable — use rule fallback (no crash)
            triage = _rule_triage(list(collected_symptoms))
            log.info(f"[{session_id}] Neo4j unavailable, using rule fallback")

        top_conditions = triage.get("possible_conditions", [])

        # ── Step 6: Updated Neo4j Graph — write session node ──────────────────
        await _update_neo4j_session_node(
            session_id,
            list(collected_symptoms),
            triage["urgency_level"],
        )

        # ── Step 7: Decide — finalize or ask follow-up ────────────────────────
        is_final = should_finalize(turn_count, triage["urgency_level"], len(collected_symptoms))

    # ── Step 8: Build reply ───────────────────────────────────────────────────
    reply_text = ""

    if is_final:
        reply_text = build_safe_diagnosis(top_conditions)
    else:
        # LLM / Neo4j discriminating follow-up question
        driver = get_neo4j()
        if driver:
            async with driver.session() as s:
                neo4j_q = await generate_discriminating_question(s, top_conditions, collected_symptoms)
        else:
            neo4j_q = await generate_discriminating_question(None, top_conditions, collected_symptoms)

        # Prefer conversation-engine question (disease-specific) over Neo4j generic
        conv_q = get_next_question(top_conditions, asked_questions, turn_count)
        reply_text = conv_q or neo4j_q or "Are there any other symptoms you've noticed?"

        if reply_text not in asked_questions:
            asked_questions.append(reply_text)

    # ── Step 9: Persist session state ─────────────────────────────────────────
    turn_doc = {
        "user_input":         req.user_input,
        "bot_reply":          reply_text,
        "extracted_entities": entities,
        "symptoms_this_turn": new_symptoms,
        "timestamp":          now,
    }

    update_payload: dict = {
        "$setOnInsert": {
            "session_id":   session_id,
            "created_at":   now,
            "patient_info": req.patient_info,
        },
        "$set": {
            "collected_symptoms": list(collected_symptoms),
            "turn_count":         turn_count + 1,
            "asked_questions":    asked_questions,
            "asked_clarifications": asked_clarifications,
            "status":             "completed" if is_final else "active",
        },
        "$push": {"conversation": turn_doc},
    }

    if is_final:
        triage["triaged_at"] = now
        triage["overridden"] = False
        update_payload["$set"]["triage_result"] = triage

        # Build and store handoff report
        report = _build_handoff_report(session_id, req.patient_info, req.user_input, entities, triage)
        await db.handoff_reports.insert_one(report)

    await db.patient_sessions.update_one(
        {"session_id": session_id}, update_payload, upsert=True
    )

    # ── Step 10: Return conversational response ───────────────────────────────
    response: dict = {
        "session_id":         session_id,
        "reply":              reply_text,
        "extracted_entities": entities,
        "neo4j_nodes":        list(collected_symptoms),
        "turn":               turn_count + 1,
        "questions_remaining": max(0, MAX_QUESTIONS - turn_count - 1),
        "triage":             triage if is_final else None,
    }

    if is_final:
        safe = build_safe_response(
            top_conditions,
            triage["urgency_level"],
            triage["recommended_action"],
            None,
            True,
        )
        response["urgency_summary"] = safe
        response["disclaimer"] = safe["disclaimer"]

    return response


# ── GET /chat/{session_id} ────────────────────────────────────────────────────

@router.get("/{session_id}", summary="Get session conversation + triage result")
async def get_chat(session_id: str, request: Request):
    db      = request.app.state.db
    session = await db.patient_sessions.find_one({"session_id": session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session.pop("_id", None)
    return session


# ── PUT /chat/{session_id} ────────────────────────────────────────────────────

@router.put("/{session_id}", summary="Update patient info on a session")
async def update_patient_info(session_id: str, req: UpdatePatientRequest, request: Request):
    db      = request.app.state.db
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
