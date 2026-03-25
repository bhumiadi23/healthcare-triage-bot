"""
MongoDB Connection — Healthcare Triage Bot
Uses motor (async PyMongo) for FastAPI compatibility
"""
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/triage_db")
DB_NAME = os.getenv("MONGO_DB_NAME", "triage_db")

client: AsyncIOMotorClient = None


def get_client() -> AsyncIOMotorClient:
    return AsyncIOMotorClient(MONGO_URI)


def get_db():
    return get_client()[DB_NAME]


async def connect_db():
    global client
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]
    await create_indexes(db)
    print(f"[DB] MongoDB connected: {MONGO_URI} | DB: {DB_NAME}")
    return db


async def close_db():
    global client
    if client:
        client.close()
        print("[DB] MongoDB connection closed.")


async def create_indexes(db):
    await db.patient_sessions.create_index("session_id", unique=True)
    await db.patient_sessions.create_index([("created_at", -1)])
    await db.handoff_reports.create_index("session_id")
    await db.handoff_reports.create_index([("generated_at", -1)])
    print("[DB] Indexes ensured.")
