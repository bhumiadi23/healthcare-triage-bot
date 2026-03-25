"""
MongoDB Connection Test — run this to verify everything works
Usage: python test_connection.py
"""
import asyncio
from datetime import datetime, timezone

def utcnow(): return datetime.now(timezone.utc)
from database import connect_db, close_db, get_client
from dotenv import load_dotenv
import os

load_dotenv()


async def test():
    print("\n[TEST] Testing MongoDB connection...\n")

    # 1. Connect
    db = await connect_db()

    # 2. Insert a sample patient session
    sample_session = {
        "session_id": "test-session-001",
        "created_at": utcnow(),
        "patient_info": {"age": 35, "sex": "M", "known_conditions": []},
        "conversation": [
            {
                "turn": 1,
                "user_input": "I have chest pain and shortness of breath",
                "extracted_entities": [
                    {"text": "chest pain", "label": "SYMPTOM", "confidence": 0.97},
                    {"text": "shortness of breath", "label": "SYMPTOM", "confidence": 0.95},
                ],
                "timestamp": utcnow(),
            }
        ],
        "triage_result": {
            "urgency_level": "CRITICAL",
            "urgency_score": 92.0,
            "possible_conditions": ["Myocardial Infarction", "Pulmonary Embolism"],
            "recommended_action": "Call 911 immediately",
            "confidence": 0.94,
        },
        "status": "completed",
    }

    # Upsert so re-runs don't fail on unique index
    await db.patient_sessions.update_one(
        {"session_id": "test-session-001"},
        {"$set": sample_session},
        upsert=True,
    )
    print("[OK] Sample session inserted/updated.")

    # 3. Read it back
    doc = await db.patient_sessions.find_one({"session_id": "test-session-001"})
    print(f"[OK] Read back session: {doc['session_id']} | urgency: {doc['triage_result']['urgency_level']}")

    # 4. List collections
    collections = await db.list_collection_names()
    print(f"[OK] Collections in '{db.name}': {collections}")

    # 5. Cleanup test doc
    await db.patient_sessions.delete_one({"session_id": "test-session-001"})
    print("[OK] Test document cleaned up.")

    await close_db()
    print("\n[PASS] All tests passed - MongoDB is connected and working!\n")


if __name__ == "__main__":
    asyncio.run(test())
