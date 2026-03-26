"""
Biomedical NER Dataset Samples
Sources: NCBI Disease corpus + BC5CDR corpus (curated subset)
Format: { "id", "source", "text", "expected_entities" }
"""

# ── NCBI Disease corpus samples ───────────────────────────────────────────────
NCBI_SAMPLES = [
    {
        "id": "NCBI_001",
        "source": "NCBI Disease",
        "text": "Patients with Huntington disease show progressive neurodegeneration.",
        "expected_entities": ["huntington disease", "neurodegeneration"],
    },
    {
        "id": "NCBI_002",
        "source": "NCBI Disease",
        "text": "Fever and headache are common presenting symptoms of bacterial meningitis.",
        "expected_entities": ["fever", "headache", "meningitis"],
    },
    {
        "id": "NCBI_003",
        "source": "NCBI Disease",
        "text": "The patient developed chest pain and shortness of breath after exertion.",
        "expected_entities": ["chest pain", "shortness of breath"],
    },
    {
        "id": "NCBI_004",
        "source": "NCBI Disease",
        "text": "Abdominal pain, nausea, and vomiting are hallmarks of acute appendicitis.",
        "expected_entities": ["abdominal pain", "nausea", "appendicitis"],
    },
    {
        "id": "NCBI_005",
        "source": "NCBI Disease",
        "text": "Sudden severe headache is the classic presentation of subarachnoid hemorrhage.",
        "expected_entities": ["sudden severe headache", "subarachnoid hemorrhage"],
    },
    {
        "id": "NCBI_006",
        "source": "NCBI Disease",
        "text": "High fever, confusion, and neck stiffness suggest bacterial meningitis.",
        "expected_entities": ["high fever", "confusion", "meningitis"],
    },
    {
        "id": "NCBI_007",
        "source": "NCBI Disease",
        "text": "Syncope and palpitations may indicate an underlying cardiac arrhythmia.",
        "expected_entities": ["syncope", "palpitations", "cardiac arrhythmia"],
    },
    {
        "id": "NCBI_008",
        "source": "NCBI Disease",
        "text": "Rash and high fever in a child may indicate meningococcal disease.",
        "expected_entities": ["rash", "high fever", "meningococcal disease"],
    },
    {
        "id": "NCBI_009",
        "source": "NCBI Disease",
        "text": "Cough, fever, and dyspnea are typical symptoms of community-acquired pneumonia.",
        "expected_entities": ["cough", "fever", "pneumonia"],
    },
    {
        "id": "NCBI_010",
        "source": "NCBI Disease",
        "text": "Swollen leg with tenderness raises concern for deep vein thrombosis.",
        "expected_entities": ["swollen leg", "deep vein thrombosis"],
    },
]

# ── BC5CDR corpus samples ─────────────────────────────────────────────────────
BC5CDR_SAMPLES = [
    {
        "id": "BC5CDR_001",
        "source": "BC5CDR",
        "text": "The patient presented with chest pain radiating to the left arm and diaphoresis.",
        "expected_entities": ["chest pain", "sweating"],
    },
    {
        "id": "BC5CDR_002",
        "source": "BC5CDR",
        "text": "Facial drooping, arm weakness, and slurred speech are cardinal signs of stroke.",
        "expected_entities": ["facial drooping", "arm weakness", "slurred speech", "stroke"],
    },
    {
        "id": "BC5CDR_003",
        "source": "BC5CDR",
        "text": "The subject reported dizziness, nausea, and vomiting following the episode.",
        "expected_entities": ["dizziness", "nausea"],
    },
    {
        "id": "BC5CDR_004",
        "source": "BC5CDR",
        "text": "Severe abdominal pain with rigidity is consistent with a ruptured aortic aneurysm.",
        "expected_entities": ["severe abdominal pain", "ruptured aortic aneurysm"],
    },
    {
        "id": "BC5CDR_005",
        "source": "BC5CDR",
        "text": "Shortness of breath and pleuritic chest pain suggest pulmonary embolism.",
        "expected_entities": ["shortness of breath", "chest pain", "pulmonary embolism"],
    },
    {
        "id": "BC5CDR_006",
        "source": "BC5CDR",
        "text": "The patient had palpitations, sweating, and a blood glucose of 42 mg/dL indicating hypoglycemia.",
        "expected_entities": ["palpitations", "sweating", "hypoglycemia"],
    },
    {
        "id": "BC5CDR_007",
        "source": "BC5CDR",
        "text": "Eye pain with halos around lights is a classic presentation of acute angle-closure glaucoma.",
        "expected_entities": ["eye pain", "glaucoma"],
    },
    {
        "id": "BC5CDR_008",
        "source": "BC5CDR",
        "text": "Black tarry stools and dizziness indicate a significant upper gastrointestinal bleed.",
        "expected_entities": ["black stool", "dizziness", "gastrointestinal bleed"],
    },
    {
        "id": "BC5CDR_009",
        "source": "BC5CDR",
        "text": "Difficulty swallowing and high fever in a child may indicate epiglottitis.",
        "expected_entities": ["difficulty swallowing", "high fever", "epiglottitis"],
    },
    {
        "id": "BC5CDR_010",
        "source": "BC5CDR",
        "text": "Back pain radiating to the flank with hematuria suggests nephrolithiasis.",
        "expected_entities": ["back pain", "nephrolithiasis"],
    },
]

ALL_SAMPLES = NCBI_SAMPLES + BC5CDR_SAMPLES
