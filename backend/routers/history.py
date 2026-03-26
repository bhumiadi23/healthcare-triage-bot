"""
GET /history              — List all sessions (paginated)
GET /history/{session_id} — Get full session detail
PUT /history/{session_id} — Update session status
GET /history/stats/summary — Urgency breakdown stats
"""
from fastapi import APIRouter, Request, HTTPException, Query
from pydantic import BaseModel

router = APIRouter()


class StatusUpdate(BaseModel):
    status: str  # active | completed | abandoned


# GET — list all sessions (paginated)
@router.get("", summary="List all patient sessions")
async def list_sessions(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    status: str | None = Query(None),
    urgency: str | None = Query(None),
):
    db = request.app.state.db
    query = {}
    if status:
        query["status"] = status
    if urgency:
        query["triage_result.urgency_level"] = urgency.upper()

    skip = (page - 1) * limit
    cursor = db.patient_sessions.find(query, {"conversation": 0}).sort("created_at", -1).skip(skip).limit(limit)
    sessions = await cursor.to_list(length=limit)
    total = await db.patient_sessions.count_documents(query)

    for s in sessions:
        s.pop("_id", None)

    return {
        "page":     page,
        "limit":    limit,
        "total":    total,
        "sessions": sessions,
    }


# GET — single session detail
@router.get("/stats/summary", summary="Urgency breakdown statistics")
async def stats_summary(request: Request):
    db = request.app.state.db
    pipeline = [
        {"$group": {"_id": "$triage_result.urgency_level", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    result = await db.patient_sessions.aggregate(pipeline).to_list(length=10)
    total  = await db.patient_sessions.count_documents({})

    breakdown = {r["_id"]: r["count"] for r in result if r["_id"]}
    return {
        "total_sessions": total,
        "urgency_breakdown": {
            "CRITICAL": breakdown.get("CRITICAL", 0),
            "HIGH":     breakdown.get("HIGH",     0),
            "MEDIUM":   breakdown.get("MEDIUM",   0),
            "LOW":      breakdown.get("LOW",      0),
        },
    }


@router.get("/{session_id}", summary="Get full session detail")
async def get_session(session_id: str, request: Request):
    db = request.app.state.db
    session = await db.patient_sessions.find_one({"session_id": session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session.pop("_id", None)
    return session


# PUT — update session status
@router.put("/{session_id}", summary="Update session status")
async def update_status(session_id: str, req: StatusUpdate, request: Request):
    db = request.app.state.db
    valid = {"active", "completed", "abandoned"}
    if req.status not in valid:
        raise HTTPException(status_code=400, detail=f"Status must be one of: {valid}")

    result = await db.patient_sessions.update_one(
        {"session_id": session_id},
        {"$set": {"status": req.status}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"session_id": session_id, "status": req.status, "message": "Session status updated."}
