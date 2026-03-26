"""
Seed 100 realistic patient sessions + triage results + handoff reports
Run: python seed_data.py
"""
import asyncio
import uuid
import random
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/triage_db")
DB_NAME   = os.getenv("MONGO_DB_NAME", "triage_db")

# --- Patient profiles ---
AGES   = list(range(5, 90))
SEXES  = ["M", "F", "Other"]
CONDITIONS = [
    [], [], [],  # most have none
    ["Hypertension"], ["Diabetes Type 2"], ["Asthma"],
    ["Hypertension", "Diabetes Type 2"], ["Heart Disease"],
    ["COPD"], ["Obesity"], ["Anxiety Disorder"],
]

# --- Symptom scenarios ---
SCENARIOS = [
    # (symptoms_list, urgency, conditions, action, score, confidence)
    (["chest pain", "sweating", "shortness of breath"],   "CRITICAL", ["Myocardial Infarction", "Angina"],              "Call 108 immediately",            92, 0.95),
    (["facial drooping", "arm weakness", "slurred speech"],"CRITICAL", ["Stroke"],                                       "Call 108 immediately",            92, 0.98),
    (["sudden severe headache", "confusion"],              "CRITICAL", ["Subarachnoid Hemorrhage", "Meningitis"],         "Call 108 immediately",            92, 0.94),
    (["vomiting blood"],                                   "CRITICAL", ["GI Bleed"],                                     "Call 108 immediately",            92, 0.95),
    (["severe abdominal pain", "sweating"],                "CRITICAL", ["Ruptured Aortic Aneurysm", "Appendicitis"],     "Call 108 immediately",            92, 0.91),
    (["syncope", "palpitations"],                          "CRITICAL", ["Cardiac Arrhythmia", "Atrial Fibrillation"],    "Call 108 immediately",            92, 0.90),
    (["difficulty swallowing", "high fever"],              "CRITICAL", ["Epiglottitis"],                                 "Call 108 immediately",            92, 0.90),
    (["rash", "high fever", "confusion"],                  "CRITICAL", ["Meningococcemia", "Sepsis"],                    "Call 108 immediately",            92, 0.92),
    (["chest pain", "shortness of breath"],                "CRITICAL", ["Pulmonary Embolism", "Myocardial Infarction"],  "Call 108 immediately",            92, 0.93),
    (["arm weakness", "confusion", "dizziness"],           "CRITICAL", ["Stroke", "TIA"],                               "Call 108 immediately",            92, 0.92),
    (["shortness of breath", "sweating", "palpitations"],  "HIGH",     ["Pulmonary Embolism", "Asthma Attack"],          "Go to the ER now",                70, 0.85),
    (["abdominal pain", "fever", "nausea"],                "HIGH",     ["Appendicitis", "Gastroenteritis"],              "Go to the ER now",                70, 0.82),
    (["high fever", "confusion"],                          "HIGH",     ["Sepsis", "Meningitis"],                         "Go to the ER now",                70, 0.83),
    (["swollen leg", "back pain"],                         "HIGH",     ["Deep Vein Thrombosis", "Kidney Stone"],         "Go to the ER now",                70, 0.84),
    (["eye pain", "headache"],                             "HIGH",     ["Acute Angle-Closure Glaucoma", "Migraine"],     "Go to the ER now",                70, 0.83),
    (["black stool", "dizziness"],                         "HIGH",     ["GI Bleed"],                                     "Go to the ER now",                70, 0.88),
    (["palpitations", "shortness of breath"],              "HIGH",     ["Atrial Fibrillation", "Anxiety"],               "Go to the ER now",                70, 0.82),
    (["back pain", "fever", "nausea"],                     "HIGH",     ["Kidney Stone", "Pyelonephritis"],               "Go to the ER now",                70, 0.80),
    (["abdominal pain", "sweating"],                       "HIGH",     ["Appendicitis", "Bowel Obstruction"],            "Go to the ER now",                70, 0.81),
    (["confusion", "high fever"],                          "HIGH",     ["Sepsis", "Encephalitis"],                       "Go to the ER now",                70, 0.84),
    (["headache", "fever", "nausea"],                      "MEDIUM",   ["Migraine", "Influenza"],                        "Visit urgent care within 4 hours",40, 0.75),
    (["cough", "fever"],                                   "MEDIUM",   ["Pneumonia", "COVID-19", "Influenza"],           "Visit urgent care within 4 hours",40, 0.72),
    (["dizziness", "nausea"],                              "MEDIUM",   ["Vertigo", "Labyrinthitis"],                     "Visit urgent care within 4 hours",40, 0.70),
    (["fever", "back pain"],                               "MEDIUM",   ["UTI", "Pyelonephritis"],                        "Visit urgent care within 4 hours",40, 0.71),
    (["rash", "fever"],                                    "MEDIUM",   ["Allergic Reaction", "Viral Exanthem"],          "Visit urgent care within 4 hours",40, 0.73),
    (["abdominal pain", "nausea"],                         "MEDIUM",   ["Gastroenteritis", "IBS"],                       "Visit urgent care within 4 hours",40, 0.70),
    (["shortness of breath", "cough"],                     "MEDIUM",   ["Asthma", "Bronchitis"],                         "Visit urgent care within 4 hours",40, 0.72),
    (["palpitations"],                                     "MEDIUM",   ["Anxiety", "Arrhythmia"],                        "Visit urgent care within 4 hours",40, 0.68),
    (["headache", "dizziness"],                            "MEDIUM",   ["Migraine", "Hypertension"],                     "Visit urgent care within 4 hours",40, 0.70),
    (["fever", "cough", "body aches"],                     "MEDIUM",   ["Influenza", "COVID-19"],                        "Visit urgent care within 4 hours",40, 0.74),
    (["back pain"],                                        "LOW",      ["Muscle Strain", "Lumbar Sprain"],               "Schedule a GP appointment",       15, 0.85),
    (["headache"],                                         "LOW",      ["Tension Headache", "Dehydration"],              "Schedule a GP appointment",       15, 0.82),
    (["cough"],                                            "LOW",      ["Common Cold", "Allergies"],                     "Schedule a GP appointment",       15, 0.88),
    (["nausea"],                                           "LOW",      ["Indigestion", "Motion Sickness"],               "Schedule a GP appointment",       15, 0.80),
    (["dizziness"],                                        "LOW",      ["Dehydration", "Orthostatic Hypotension"],       "Schedule a GP appointment",       15, 0.78),
    (["rash"],                                             "LOW",      ["Contact Dermatitis", "Eczema"],                 "Schedule a GP appointment",       15, 0.82),
    (["fever"],                                            "LOW",      ["Common Cold", "Viral Infection"],               "Schedule a GP appointment",       15, 0.80),
    (["back pain", "nausea"],                              "LOW",      ["Muscle Strain", "Indigestion"],                 "Schedule a GP appointment",       15, 0.78),
    (["headache", "nausea"],                               "LOW",      ["Tension Headache", "Dehydration"],              "Schedule a GP appointment",       15, 0.79),
    (["cough", "nausea"],                                  "LOW",      ["Common Cold", "Post-nasal Drip"],               "Schedule a GP appointment",       15, 0.77),
]

FREE_TEXT_TEMPLATES = [
    "I have {symptoms} since yesterday.",
    "I've been experiencing {symptoms} for the past few hours.",
    "Feeling {symptoms}, it started this morning.",
    "I woke up with {symptoms}.",
    "I suddenly developed {symptoms}.",
    "My {symptoms} has been getting worse.",
    "I've had {symptoms} for 2 days now.",
    "I'm suffering from {symptoms} and it's quite severe.",
]


def make_session(scenario_idx: int) -> tuple[dict, dict]:
    symptoms, urgency, conditions, action, score, confidence = SCENARIOS[scenario_idx % len(SCENARIOS)]
    session_id = str(uuid.uuid4())
    age        = random.choice(AGES)
    sex        = random.choice(SEXES)
    known      = random.choice(CONDITIONS)

    symptom_text = " and ".join(symptoms)
    template     = random.choice(FREE_TEXT_TEMPLATES)
    user_input   = template.format(symptoms=symptom_text)

    created_at = datetime.now(timezone.utc) - timedelta(
        days=random.randint(0, 30),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
    )

    session = {
        "session_id":   session_id,
        "created_at":   created_at,
        "patient_info": {"age": age, "sex": sex, "known_conditions": known},
        "conversation": [
            {
                "turn": 1,
                "user_input": user_input,
                "extracted_entities": [
                    {"text": s, "label": "SYMPTOM", "confidence": round(random.uniform(0.85, 0.99), 2)}
                    for s in symptoms
                ],
                "timestamp": created_at,
            }
        ],
        "triage_result": {
            "urgency_level":       urgency,
            "urgency_score":       score,
            "possible_conditions": conditions,
            "recommended_action":  action,
            "confidence":          confidence,
            "triaged_at":          created_at + timedelta(seconds=random.randint(3, 10)),
        },
        "status": "completed",
    }

    report = {
        "report_id":    str(uuid.uuid4()),
        "session_id":   session_id,
        "generated_at": created_at + timedelta(seconds=15),
        "patient_summary": {"age": age, "sex": sex, "known_conditions": known},
        "chief_complaint": user_input,
        "extracted_symptoms": [
            {"symptom": s, "severity": random.choice(["mild", "moderate", "severe"]), "duration": None}
            for s in symptoms
        ],
        "differential_diagnosis": [
            {"condition": c, "probability": round(confidence * (0.9 ** i), 2), "icd10_code": None}
            for i, c in enumerate(conditions)
        ],
        "triage_decision": {
            "urgency_level":      urgency,
            "recommended_action": action,
            "assigned_at":        created_at + timedelta(seconds=15),
        },
        "vital_flags":    ["Requires immediate physician review"] if urgency == "CRITICAL" else [],
        "report_pdf_url": None,
    }

    return session, report


async def seed():
    client = AsyncIOMotorClient(MONGO_URI)
    db     = client[DB_NAME]

    sessions = []
    reports  = []
    for i in range(100):
        session, report = make_session(i)
        sessions.append(session)
        reports.append(report)

    await db.patient_sessions.insert_many(sessions)
    await db.handoff_reports.insert_many(reports)

    print(f"[OK] Inserted 100 patient sessions into '{DB_NAME}.patient_sessions'")
    print(f"[OK] Inserted 100 handoff reports into '{DB_NAME}.handoff_reports'")

    # Summary breakdown
    urgency_counts = {}
    for s in sessions:
        lvl = s["triage_result"]["urgency_level"]
        urgency_counts[lvl] = urgency_counts.get(lvl, 0) + 1
    print("\nUrgency breakdown:")
    for lvl in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        print(f"  {lvl}: {urgency_counts.get(lvl, 0)}")

    client.close()


if __name__ == "__main__":
    asyncio.run(seed())
