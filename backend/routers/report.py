"""
POST /report              — Generate Doctor Handoff Report
GET  /report/{session_id} — Retrieve latest report for a session
PUT  /report/{report_id}  — Update vital flags or doctor notes on a report
"""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

router = APIRouter()


class ReportRequest(BaseModel):
    session_id: str


class UpdateReportRequest(BaseModel):
    vital_flags: list[str] | None = None
    doctor_notes: str | None = None
    report_pdf_url: str | None = None


# POST — generate report
@router.post("", summary="Generate Doctor Handoff Report from a completed session")
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
        "vital_flags":    ["Requires immediate physician review"] if triage["urgency_level"] == "CRITICAL" else [],
        "doctor_notes":   None,
        "report_pdf_url": None,
    }

    await db.handoff_reports.insert_one(report)
    report.pop("_id", None)
    return report


# GET — retrieve latest report
@router.get("/{session_id}", summary="Get latest handoff report for a session")
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


# PUT — update vital flags / doctor notes
@router.put("/{report_id}", summary="Update vital flags or doctor notes on a report")
async def update_report(report_id: str, req: UpdateReportRequest, request: Request):
    db = request.app.state.db
    report = await db.handoff_reports.find_one({"report_id": report_id})
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    updates["updated_at"] = datetime.now(timezone.utc)
    await db.handoff_reports.update_one({"report_id": report_id}, {"$set": updates})

    return {"report_id": report_id, "updated": list(updates.keys()), "message": "Report updated successfully."}
