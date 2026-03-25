"""
POST /chat — Receive symptom text, extract entities (mock NER), save to MongoDB
"""
from fastapi import APIRouter, Request
from pydantic import BaseModel
from datetime import datetime, timezone
import uuid

router = APIRouter()


class ChatRequest(BaseModel):
    session_id: str | None = None
    user_input: str
    patient_info: dict = {}


# Mock NER — replaced by BioBERT on Day 2
SYMPTOM_KEYWORDS = [
    "chest pain", "shortness of breath", "sweating", "headache",
    "sudden severe headache", "facial drooping", "arm weakness",
    "slurred speech", "confusion", "high fever", "fever", "abdominal pain",
    "severe abdominal pain", "nausea", "vomiting blood", "black stool",
    "dizziness", "palpitations", "syncope", "cough", "rash",
    "swollen leg", "back pain", "difficulty swallowing", "eye pain",
]

def mock_ner(text: str) -> list[dict]:
    text_lower = text.lower()
    return [
        {"text": kw, "label": "SYMPTOM", "confidence": 0.90}
        for kw in SYMPTOM_KEYWORDS if kw in text_lower
    ]


@router.post("")
async def chat(req: ChatRequest, request: Request):
    db = request.app.state.db

    session_id = req.session_id or str(uuid.uuid4())
    entities = mock_ner(req.user_input)

    turn = {
        "user_input": req.user_input,
        "extracted_entities": entities,
        "timestamp": datetime.now(timezone.utc),
    }

    # Upsert session — push new conversation turn
    result = await db.patient_sessions.find_one_and_update(
        {"session_id": session_id},
        {
            "$setOnInsert": {
                "session_id": session_id,
                "created_at": datetime.now(timezone.utc),
                "patient_info": req.patient_info,
                "status": "active",
                "triage_result": None,
            },
            "$push": {"conversation": turn},
        },
        upsert=True,
        return_document=True,
    )

    return {
        "session_id": session_id,
        "extracted_entities": entities,
        "turn": len(result.get("conversation", [])) if result else 1,
    }
