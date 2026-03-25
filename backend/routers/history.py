"""
GET /history/{session_id} — Retrieve full patient session history
"""
from fastapi import APIRouter, Request, HTTPException

router = APIRouter()


@router.get("/{session_id}")
async def get_history(session_id: str, request: Request):
    db = request.app.state.db

    session = await db.patient_sessions.find_one({"session_id": session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.pop("_id", None)
    return session
