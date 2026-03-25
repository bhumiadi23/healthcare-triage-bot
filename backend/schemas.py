"""
MongoDB Schema Definitions — Healthcare Triage Bot
Uses Pydantic v2 for validation + PyMongo for DB operations
"""
from datetime import datetime, timezone

def utcnow(): return datetime.now(timezone.utc)
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
import uuid


class UrgencyLevel(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class EntityLabel(str, Enum):
    SYMPTOM = "SYMPTOM"
    CONDITION = "CONDITION"
    BODY_PART = "BODY_PART"


class ExtractedEntity(BaseModel):
    text: str
    label: EntityLabel
    confidence: float = Field(ge=0.0, le=1.0)


class ConversationTurn(BaseModel):
    turn: int
    user_input: str
    extracted_entities: list[ExtractedEntity] = []
    timestamp: datetime = Field(default_factory=utcnow)


class PatientInfo(BaseModel):
    age: Optional[int] = None
    sex: Optional[str] = None
    known_conditions: list[str] = []


class TriageResult(BaseModel):
    urgency_level: UrgencyLevel
    urgency_score: float = Field(ge=0, le=100)
    possible_conditions: list[str]
    recommended_action: str
    confidence: float = Field(ge=0.0, le=1.0)


class PatientSession(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=utcnow)
    patient_info: PatientInfo = Field(default_factory=PatientInfo)
    conversation: list[ConversationTurn] = []
    triage_result: Optional[TriageResult] = None
    status: str = "active"  # active | completed | abandoned


# --- Handoff Report ---

class SymptomDetail(BaseModel):
    symptom: str
    duration: Optional[str] = None
    severity: Optional[str] = None  # mild | moderate | severe


class DifferentialDiagnosis(BaseModel):
    condition: str
    probability: float = Field(ge=0.0, le=1.0)
    icd10_code: Optional[str] = None


class TriageDecision(BaseModel):
    urgency_level: UrgencyLevel
    recommended_action: str
    assigned_at: datetime = Field(default_factory=utcnow)


class HandoffReport(BaseModel):
    report_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    generated_at: datetime = Field(default_factory=utcnow)
    patient_summary: PatientInfo
    chief_complaint: str
    extracted_symptoms: list[SymptomDetail]
    differential_diagnosis: list[DifferentialDiagnosis]
    triage_decision: TriageDecision
    vital_flags: list[str] = []
    report_pdf_url: Optional[str] = None


# --- MongoDB Index Setup ---

def create_indexes(db):
    db.patient_sessions.create_index("session_id", unique=True)
    db.patient_sessions.create_index([("created_at", -1)])
    db.handoff_reports.create_index("session_id")
    db.handoff_reports.create_index([("generated_at", -1)])
