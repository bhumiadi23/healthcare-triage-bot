"""
POST /report        — Generate Doctor Handoff Report from a completed session
GET  /report/{id}   — Retrieve an existing report
"""
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from datetime import datetime, timezone
import uuid

router = APIRouter()


class ReportRequest(BaseModel):
    session_id: str


@router.post("")
async def generate_report(req: ReportRequest, request: Request):
    db = request.app.state.db

    session = await db.patient_sessions.find_one({"session_id": req.session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not session.get("triage_result"):
        raise HTTPException(status_code=400, detail="Run /triage before generating a report")

    triage = session["triage_result"]
    all_entities = [
        e for turn in session.get("conversation", [])
        for e in turn.get("extracted_entities", [])
    ]
    unique_symptoms = list({e["text"]: e for e in all_entities}.values())

    report = {
        "report_id":    str(uuid.uuid4()),
        "session_id":   req.session_id,
        "generated_at": datetime.now(timezone.utc),
        "patient_summary": session.get("patient_info", {}),
        "chief_complaint": session["conversation"][0]["user_input"] if session.get("conversation") else "",
        "extracted_symptoms": [
            {"symptom": e["text"], "severity": None, "duration": None}
            for e in unique_symptoms
        ],
        "differential_diagnosis": [
            {"condition": c, "probability": round(triage["confidence"] * 0.9 ** i, 2), "icd10_code": None}
            for i, c in enumerate(triage.get("possible_conditions", []))
        ],
        "triage_decision": {
            "urgency_level":      triage["urgency_level"],
            "recommended_action": triage["recommended_action"],
            "assigned_at":        datetime.now(timezone.utc),
        },
        "vital_flags":    ["Requires immediate physician review"] if triage["urgency_level"] == "CRITICAL" else [],
        "report_pdf_url": None,
    }

    await db.handoff_reports.insert_one(report)
    report.pop("_id", None)
    return report


@router.get("/{session_id}")
async def get_report(session_id: str, request: Request):
    db = request.app.state.db

    report = await db.handoff_reports.find_one(
        {"session_id": session_id},
        sort=[("generated_at", -1)],
    )
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    report.pop("_id", None)
    return report
