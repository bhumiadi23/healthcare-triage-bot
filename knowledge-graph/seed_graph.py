"""
Neo4j Knowledge Graph Seed — Full MVP Graph
Nodes: Symptom, Disease, RiskFactor, UrgencyLevel
Edges: INDICATES, HAS_URGENCY, HAS_RISK_FACTOR, CO_OCCURS_WITH
Run: python seed_graph.py
"""
from neo4j import GraphDatabase
from dotenv import load_dotenv
import os, ssl, certifi

load_dotenv()

URI  = os.getenv("NEO4J_URI",      "neo4j+s://13e3e3f7.databases.neo4j.io")
AUTH = (os.getenv("NEO4J_USER",    "neo4j"),
        os.getenv("NEO4J_PASSWORD", "password"))

# ── Urgency levels ────────────────────────────────────────────────────────────
URGENCY_SCORES = {"CRITICAL": 92, "HIGH": 70, "MEDIUM": 40, "LOW": 15}

URGENCY_ACTION = {
    "CRITICAL": "Call 108 immediately",
    "HIGH":     "Go to the ER now",
    "MEDIUM":   "Visit urgent care within 4 hours",
    "LOW":      "Schedule a GP appointment",
}

# ── Top-50 symptom → disease → urgency ───────────────────────────────────────
SYMPTOM_DISEASE_MAP = [
    # Cardiology
    ("chest pain",             "Myocardial Infarction",       "CRITICAL", 0.95),
    ("chest pain",             "Angina",                      "HIGH",     0.75),
    ("chest pain",             "GERD",                        "LOW",      0.40),
    ("chest pain",             "Pulmonary Embolism",          "CRITICAL", 0.80),
    ("chest pain",             "Pericarditis",                "HIGH",     0.65),
    ("chest tightness",        "Asthma Attack",               "HIGH",     0.85),
    ("chest tightness",        "Anxiety",                     "LOW",      0.50),
    ("shortness of breath",    "Pulmonary Embolism",          "CRITICAL", 0.90),
    ("shortness of breath",    "Asthma Attack",               "HIGH",     0.80),
    ("shortness of breath",    "Pneumonia",                   "HIGH",     0.70),
    ("shortness of breath",    "Anxiety",                     "MEDIUM",   0.50),
    ("shortness of breath",    "Heart Failure",               "HIGH",     0.85),
    ("sweating",               "Myocardial Infarction",       "CRITICAL", 0.85),
    ("sweating",               "Hypoglycemia",                "HIGH",     0.75),
    ("sweating",               "Hyperthyroidism",             "LOW",      0.50),
    ("palpitations",           "Atrial Fibrillation",         "HIGH",     0.85),
    ("palpitations",           "Anxiety",                     "LOW",      0.60),
    ("palpitations",           "Hyperthyroidism",             "MEDIUM",   0.70),
    ("syncope",                "Cardiac Arrhythmia",          "CRITICAL", 0.90),
    ("syncope",                "Vasovagal Syncope",           "MEDIUM",   0.70),
    
    # Neurology
    ("sudden severe headache", "Subarachnoid Hemorrhage",     "CRITICAL", 0.95),
    ("sudden severe headache", "Meningitis",                  "CRITICAL", 0.90),
    ("headache",               "Migraine",                    "MEDIUM",   0.70),
    ("headache",               "Tension Headache",            "LOW",      0.80),
    ("headache",               "Hypertensive Crisis",         "HIGH",     0.65),
    ("headache",               "Dehydration",                 "LOW",      0.60),
    ("facial drooping",        "Stroke",                      "CRITICAL", 0.98),
    ("arm weakness",           "Stroke",                      "CRITICAL", 0.95),
    ("leg weakness",           "Stroke",                      "CRITICAL", 0.90),
    ("slurred speech",         "Stroke",                      "CRITICAL", 0.95),
    ("confusion",              "Stroke",                      "CRITICAL", 0.85),
    ("confusion",              "Sepsis",                      "CRITICAL", 0.80),
    ("confusion",              "Hypoglycemia",                "HIGH",     0.75),
    ("confusion",              "Urinary Tract Infection",     "MEDIUM",   0.65), # Especially in elderly
    ("dizziness",              "Stroke",                      "CRITICAL", 0.75),
    ("dizziness",              "Hypoglycemia",                "HIGH",     0.70),
    ("dizziness",              "Vertigo",                     "MEDIUM",   0.80),
    ("dizziness",              "Dehydration",                 "LOW",      0.65),
    ("numbness",               "Stroke",                      "CRITICAL", 0.85),
    ("numbness",               "Diabetic Neuropathy",         "LOW",      0.70),
    ("tremor",                 "Parkinson's Disease",         "LOW",      0.80),
    ("tremor",                 "Essential Tremor",            "LOW",      0.75),

    # Infectious / Respiratory
    ("high fever",             "Sepsis",                      "CRITICAL", 0.80),
    ("high fever",             "Meningitis",                  "CRITICAL", 0.85),
    ("high fever",             "Influenza",                   "MEDIUM",   0.70),
    ("high fever",             "COVID-19",                    "MEDIUM",   0.75),
    ("fever",                  "Urinary Tract Infection",     "MEDIUM",   0.65),
    ("fever",                  "Common Cold",                 "LOW",      0.80),
    ("fever",                  "Strep Throat",                "MEDIUM",   0.72),
    ("fever",                  "Pneumonia",                   "HIGH",     0.80),
    ("chills",                 "Influenza",                   "MEDIUM",   0.85),
    ("chills",                 "Sepsis",                      "CRITICAL", 0.75),
    ("sore throat",            "Strep Throat",                "MEDIUM",   0.90),
    ("sore throat",            "Common Cold",                 "LOW",      0.85),
    ("sore throat",            "Tonsillitis",                 "MEDIUM",   0.80),
    ("runny nose",             "Common Cold",                 "LOW",      0.95),
    ("runny nose",             "Influenza",                   "MEDIUM",   0.60),
    ("runny nose",             "Allergic Rhinitis",           "LOW",      0.85),
    ("cough",                  "Pneumonia",                   "HIGH",     0.65),
    ("cough",                  "COVID-19",                    "MEDIUM",   0.70),
    ("cough",                  "Common Cold",                 "LOW",      0.85),
    ("cough",                  "Tuberculosis",                "MEDIUM",   0.60),
    ("cough",                  "Bronchitis",                  "LOW",      0.75),
    ("coughing up blood",      "Tuberculosis",                "HIGH",     0.85),
    ("coughing up blood",      "Lung Cancer",                 "HIGH",     0.70),
    ("loss of taste",          "COVID-19",                    "LOW",      0.95),
    ("loss of smell",          "COVID-19",                    "LOW",      0.95),
    ("body aches",             "Influenza",                   "MEDIUM",   0.88),
    ("body aches",             "COVID-19",                    "MEDIUM",   0.80),
    ("body aches",             "Common Cold",                 "LOW",      0.60),

    # Gastrointestinal
    ("abdominal pain",         "Appendicitis",                "HIGH",     0.85),
    ("abdominal pain",         "Bowel Obstruction",           "HIGH",     0.80),
    ("abdominal pain",         "Food Poisoning",              "MEDIUM",   0.75),
    ("abdominal pain",         "Gastroenteritis",             "MEDIUM",   0.70),
    ("abdominal pain",         "IBS",                         "LOW",      0.60),
    ("abdominal pain",         "Peptic Ulcer",                "MEDIUM",   0.65),
    ("severe abdominal pain",  "Ruptured Aortic Aneurysm",    "CRITICAL", 0.90),
    ("nausea",                 "Myocardial Infarction",       "CRITICAL", 0.70),
    ("nausea",                 "Gastroenteritis",             "MEDIUM",   0.75),
    ("nausea",                 "Food Poisoning",              "MEDIUM",   0.85),
    ("nausea",                 "Migraine",                    "MEDIUM",   0.60),
    ("vomiting",               "Gastroenteritis",             "MEDIUM",   0.80),
    ("vomiting",               "Food Poisoning",              "MEDIUM",   0.85),
    ("vomiting blood",         "GI Bleed",                    "CRITICAL", 0.95),
    ("vomiting blood",         "Peptic Ulcer",                "HIGH",     0.85),
    ("black stool",            "GI Bleed",                    "HIGH",     0.90),
    ("diarrhea",               "Gastroenteritis",             "MEDIUM",   0.85),
    ("diarrhea",               "Food Poisoning",              "MEDIUM",   0.80),
    ("diarrhea",               "IBS",                         "LOW",      0.70),
    ("constipation",           "Bowel Obstruction",           "HIGH",     0.85),
    ("constipation",           "IBS",                         "LOW",      0.65),
    
    # Orthopedic / Musculoskeletal
    ("back pain",              "Kidney Stone",                "HIGH",     0.75),
    ("back pain",              "Muscle Strain",               "LOW",      0.85),
    ("back pain",              "Herniated Disc",              "MEDIUM",   0.70),
    ("joint pain",             "Osteoarthritis",              "LOW",      0.85),
    ("joint pain",             "Rheumatoid Arthritis",        "MEDIUM",   0.75),
    ("neck stiffness",         "Meningitis",                  "CRITICAL", 0.95),
    ("neck pain",              "Muscle Strain",               "LOW",      0.80),
    
    # Dermatological & Allergic
    ("rash",                   "Meningococcemia",             "CRITICAL", 0.90),
    ("rash",                   "Allergic Reaction",           "MEDIUM",   0.70),
    ("rash",                   "Contact Dermatitis",          "LOW",      0.85),
    ("itchy skin",             "Allergic Reaction",           "MEDIUM",   0.75),
    ("itchy skin",             "Eczema",                      "LOW",      0.80),
    ("swelling of lips",       "Anaphylaxis",                 "CRITICAL", 0.98),
    ("swelling of face",       "Anaphylaxis",                 "CRITICAL", 0.95),
    ("hives",                  "Allergic Reaction",           "MEDIUM",   0.85),
    ("hives",                  "Anaphylaxis",                 "CRITICAL", 0.75),
    
    # Other / General
    ("swollen leg",            "Deep Vein Thrombosis",        "HIGH",     0.85),
    ("painful urination",      "Urinary Tract Infection",     "MEDIUM",   0.90),
    ("frequent urination",     "Urinary Tract Infection",     "MEDIUM",   0.80),
    ("frequent urination",     "Diabetes Type 2",             "LOW",      0.75),
    ("excessive thirst",       "Diabetes Type 2",             "LOW",      0.85),
    ("difficulty swallowing",  "Epiglottitis",                "CRITICAL", 0.90),
    ("difficulty swallowing",  "Strep Throat",                "MEDIUM",   0.60),
    ("eye pain",               "Acute Angle-Closure Glaucoma","HIGH",     0.85),
    ("red eye",                "Conjunctivitis",              "LOW",      0.90),
    ("blurred vision",         "Stroke",                      "CRITICAL", 0.70),
    ("blurred vision",         "Diabetes Type 2",             "LOW",      0.65),
    ("fatigue",                "Anemia",                      "LOW",      0.75),
    ("fatigue",                "Hypothyroidism",              "LOW",      0.80),
    ("fatigue",                "Depression",                  "LOW",      0.70),
    ("fatigue",                "Heart Failure",               "MEDIUM",   0.65),
    ("unexplained weight loss","Cancer",                      "HIGH",     0.60),
    ("unexplained weight loss","Hyperthyroidism",             "MEDIUM",   0.75),
    ("weight gain",            "Hypothyroidism",              "LOW",      0.80),
]

# ── Risk factors per disease ──────────────────────────────────────────────────
DISEASE_RISK_FACTORS = [
    # (disease, risk_factor, type)
    ("Myocardial Infarction", "Hypertension",        "comorbidity"),
    ("Myocardial Infarction", "Diabetes Type 2",     "comorbidity"),
    ("Myocardial Infarction", "Smoking",             "lifestyle"),
    ("Myocardial Infarction", "Obesity",             "lifestyle"),
    ("Myocardial Infarction", "Age > 50",            "age"),
    ("Myocardial Infarction", "High Cholesterol",    "comorbidity"),
    ("Stroke",                "Hypertension",        "comorbidity"),
    ("Stroke",                "Atrial Fibrillation", "comorbidity"),
    ("Stroke",                "Diabetes Type 2",     "comorbidity"),
    ("Stroke",                "Smoking",             "lifestyle"),
    ("Stroke",                "Age > 60",            "age"),
    ("Pulmonary Embolism",    "Immobility",          "lifestyle"),
    ("Pulmonary Embolism",    "Recent Surgery",      "comorbidity"),
    ("Pulmonary Embolism",    "Cancer",              "comorbidity"),
    ("Pulmonary Embolism",    "Obesity",             "lifestyle"),
    ("Pulmonary Embolism",    "Pregnancy",           "lifestyle"),
    ("Sepsis",                "Immunocompromised",   "comorbidity"),
    ("Sepsis",                "Diabetes Type 2",     "comorbidity"),
    ("Sepsis",                "Age > 65",            "age"),
    ("Sepsis",                "Recent Surgery",      "comorbidity"),
    ("Pneumonia",             "Smoking",             "lifestyle"),
    ("Pneumonia",             "Age > 65",            "age"),
    ("Pneumonia",             "Immunocompromised",   "comorbidity"),
    ("Pneumonia",             "Asthma",              "comorbidity"),
    ("Appendicitis",          "Age 10-30",           "age"),
    ("Deep Vein Thrombosis",  "Immobility",          "lifestyle"),
    ("Deep Vein Thrombosis",  "Obesity",             "lifestyle"),
    ("Deep Vein Thrombosis",  "Recent Surgery",      "comorbidity"),
    ("Atrial Fibrillation",   "Hypertension",        "comorbidity"),
    ("Atrial Fibrillation",   "Age > 60",            "age"),
    ("Atrial Fibrillation",   "Heart Disease",       "comorbidity"),
    ("Meningitis",            "Age < 5",             "age"),
    ("Meningitis",            "Immunocompromised",   "comorbidity"),
    ("GI Bleed",              "NSAID Use",           "lifestyle"),
    ("GI Bleed",              "Alcohol Use",         "lifestyle"),
    ("GI Bleed",              "Peptic Ulcer",        "comorbidity"),
    ("Common Cold",           "Age < 5",             "age"),
    ("Common Cold",           "Immunocompromised",   "comorbidity"),
    ("Influenza",             "Age > 65",            "age"),
    ("Influenza",             "Immunocompromised",   "comorbidity"),
    ("Strep Throat",          "Age 5-15",            "age"),
    ("Strep Throat",          "Close Contact",       "lifestyle"),
    ("COVID-19",              "Age > 65",            "age"),
    ("COVID-19",              "Obesity",             "lifestyle"),
    ("COVID-19",              "Close Contact",       "lifestyle"),
    ("COVID-19",              "Immunocompromised",   "comorbidity"),
    ("Asthma Attack",         "Allergies",           "comorbidity"),
    ("Asthma Attack",         "Smoking",             "lifestyle"),
    ("Asthma Attack",         "Cold Weather",        "environmental"),
    ("Peptic Ulcer",          "NSAID Use",           "lifestyle"),
    ("Peptic Ulcer",          "H. Pylori Infection", "comorbidity"),
    ("Peptic Ulcer",          "Smoking",             "lifestyle"),
    ("Diabetic Neuropathy",   "Diabetes Type 2",     "comorbidity"),
    ("Urinary Tract Infection", "Female Gender",     "demographics"),
    ("Urinary Tract Infection", "Age > 65",          "age"),
    ("Food Poisoning",        "Undercooked Food",    "lifestyle"),
    ("Food Poisoning",        "Recent Travel",       "lifestyle"),
    ("Anaphylaxis",           "Known Allergies",     "comorbidity"),
]

# ── Co-occurring disease pairs ────────────────────────────────────────────────
CO_OCCURS = [
    ("Myocardial Infarction", "Atrial Fibrillation"),
    ("Stroke",                "Hypertensive Crisis"),
    ("Pneumonia",             "Sepsis"),
    ("Influenza",             "Pneumonia"),
    ("Common Cold",           "Strep Throat"),
    ("COVID-19",              "Pneumonia"),
    ("Diabetes Type 2",       "Diabetic Neuropathy"),
    ("Hypertension",          "Myocardial Infarction"),
    ("Atrial Fibrillation",   "Stroke"),
    ("Peptic Ulcer",          "GI Bleed"),
    ("Anxiety",               "Asthma Attack"),
    ("Heart Failure",         "Atrial Fibrillation"),
]


def seed_graph(driver):
    with driver.session() as s:

        # Urgency level nodes
        for level, score in URGENCY_SCORES.items():
            s.run("""
                MERGE (u:UrgencyLevel {level: $level})
                SET u.score = $score, u.action = $action
            """, level=level, score=score, action=URGENCY_ACTION[level])

        # Symptom → Disease → Urgency
        for symptom, disease, urgency, weight in SYMPTOM_DISEASE_MAP:
            s.run("""
                MERGE (sym:Symptom  {name: $symptom})
                MERGE (dis:Disease  {name: $disease})
                MERGE (urg:UrgencyLevel {level: $urgency})
                MERGE (sym)-[r:INDICATES]->(dis)
                  SET r.weight = $weight
                MERGE (dis)-[:HAS_URGENCY]->(urg)
            """, symptom=symptom, disease=disease, urgency=urgency, weight=weight)

        # Disease → RiskFactor
        for disease, risk, rtype in DISEASE_RISK_FACTORS:
            s.run("""
                MERGE (dis:Disease    {name: $disease})
                MERGE (rf:RiskFactor  {name: $risk})
                  SET rf.type = $rtype
                MERGE (dis)-[:HAS_RISK_FACTOR]->(rf)
            """, disease=disease, risk=risk, rtype=rtype)

        # Disease CO_OCCURS_WITH
        for d1, d2 in CO_OCCURS:
            s.run("""
                MERGE (a:Disease {name: $d1})
                MERGE (b:Disease {name: $d2})
                MERGE (a)-[:CO_OCCURS_WITH]->(b)
            """, d1=d1, d2=d2)

        total_symptoms = len({row[0] for row in SYMPTOM_DISEASE_MAP})
        total_diseases = len({row[1] for row in SYMPTOM_DISEASE_MAP})
        print(f"[OK] Seeded {total_symptoms} symptoms, {total_diseases} diseases, "
              f"{len(DISEASE_RISK_FACTORS)} risk-factor links, {len(CO_OCCURS)} co-occurrence links.")


if __name__ == "__main__":
    ssl_ctx = ssl.create_default_context(cafile=certifi.where())
    driver = GraphDatabase.driver(URI, auth=AUTH, ssl_context=ssl_ctx)
    seed_graph(driver)
    driver.close()
    print("[DONE] Neo4j Knowledge Graph ready.")
