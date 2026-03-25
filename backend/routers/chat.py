"""
POST /chat — Receive symptom text, extract entities via BioBERT NER, save to MongoDB
"""
from fastapi import APIRouter, Request
from pydantic import BaseModel
from datetime import datetime, timezone
import sys, os, uuid
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "nlp"))
from ner import extract_symptoms

router = APIRouter()


class ChatRequest(BaseModel):
    session_id: str | None = None
    user_input: str
    patient_info: dict = {}


@router.post("")
async def chat(req: ChatRequest, request: Request):
    db = request.app.state.db

    session_id = req.session_id or str(uuid.uuid4())

    # BioBERT NER extraction
    ner_result = extract_symptoms(req.user_input)
    entities = ner_result["entities"]
    neo4j_nodes = ner_result["neo4j_nodes"]

    turn = {
        "user_input":         req.user_input,
        "extracted_entities": entities,
        "neo4j_nodes":        neo4j_nodes,
        "timestamp":          datetime.now(timezone.utc),
    }

    result = await db.patient_sessions.find_one_and_update(
        {"session_id": session_id},
        {
            "$setOnInsert": {
                "session_id":   session_id,
                "created_at":   datetime.now(timezone.utc),
                "patient_info": req.patient_info,
                "status":       "active",
                "triage_result": None,
            },
            "$push": {"conversation": turn},
        },
        upsert=True,
        return_document=True,
    )

    return {
        "session_id":         session_id,
        "extracted_entities": entities,
        "neo4j_nodes":        neo4j_nodes,
        "turn":               len(result.get("conversation", [])) if result else 1,
    }
