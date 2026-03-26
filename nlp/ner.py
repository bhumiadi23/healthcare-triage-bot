"""
Medical NER Pipeline — Day 3
Uses BioBERT (dmis-lab/biobert-base-cased-v1.2) via HuggingFace for entity extraction.
Maps conversational synonyms to standardized Neo4j Symptom node names.
"""
from transformers import pipeline, AutoTokenizer, AutoModelForTokenClassification
import re

# ── Synonym map: conversational text → Neo4j Symptom node name ───────────────
SYNONYM_MAP = {
    # fever
    "hot":                    "fever",
    "burning up":             "fever",
    "temperature":            "fever",
    "running a fever":        "fever",
    "feeling feverish":       "fever",
    "feverish":               "fever",
    "fever":                  "fever",
    "chills":                 "high fever",
    "high temperature":       "high fever",

    # headache variants
    "throbbing":              "headache",
    "throbbing head":         "headache",
    "head hurts":             "headache",
    "head is pounding":       "headache",
    "pounding head":          "headache",
    "migraine":               "headache",
    "head pain":              "headache",
    "my head":                "headache",

    # chest pain variants
    "chest hurts":            "chest pain",
    "chest tightness":        "chest pain",
    "tight chest":            "chest pain",
    "pressure in chest":      "chest pain",
    "chest pressure":         "chest pain",
    "heart pain":             "chest pain",
    "chest pain":             "chest pain",
    "radiating chest":        "chest pain",

    # dyspnea / breathing
    "dyspnea":                "shortness of breath",
    "dyspnoea":               "shortness of breath",
    "can't breathe":          "shortness of breath",
    "cannot breathe":         "shortness of breath",
    "hard to breathe":        "shortness of breath",
    "trouble breathing":      "shortness of breath",
    "breathless":             "shortness of breath",
    "out of breath":          "shortness of breath",

    # nausea/vomiting
    "feel sick":              "nausea",
    "feeling sick":           "nausea",
    "want to vomit":          "nausea",
    "queasy":                 "nausea",
    "throwing up":            "nausea",
    "vomiting":               "nausea",
    "threw up":               "nausea",

    # dizziness
    "dizzy":                  "dizziness",
    "lightheaded":            "dizziness",
    "light headed":           "dizziness",
    "spinning":               "dizziness",
    "room is spinning":       "dizziness",

    # cough
    "coughing":               "cough",
    "dry cough":              "cough",
    "wet cough":              "cough",
    "keep coughing":          "cough",
    "cough":                  "cough",

    # sore throat
    "throat hurts":           "sore throat",
    "painful throat":         "sore throat",
    "scratchy throat":        "sore throat",
    "sore throat":            "sore throat",

    # abdominal pain
    "stomach pain":           "abdominal pain",
    "stomach hurts":          "abdominal pain",
    "belly pain":             "abdominal pain",
    "stomach ache":           "abdominal pain",
    "tummy ache":             "abdominal pain",
    "cramping":               "abdominal pain",

    # sweating
    "sweaty":                 "sweating",
    "drenched in sweat":      "sweating",
    "night sweats":           "sweating",
    "diaphoresis":            "sweating",
    "diaphoretic":            "sweating",
    "sweating":               "sweating",

    # body aches
    "body hurts":             "body aches",
    "everything hurts":       "body aches",
    "muscle pain":            "body aches",
    "achy":                   "body aches",
    "body aches":             "body aches",
    "aching":                 "body aches",
    "aches":                  "body aches",

    # runny nose
    "runny nose":             "runny nose",
    "nose is running":        "runny nose",
    "stuffy nose":            "runny nose",

    # back pain
    "back hurts":             "back pain",
    "lower back pain":        "back pain",

    # palpitations
    "heart racing":           "palpitations",
    "heart is racing":        "palpitations",
    "heart pounding":         "palpitations",
    "fast heartbeat":         "palpitations",
    "irregular heartbeat":    "palpitations",

    # stroke symptoms
    "face drooping":          "facial drooping",
    "face is drooping":       "facial drooping",
    "facial drooping":        "facial drooping",
    "arm is weak":            "arm weakness",
    "weak arm":               "arm weakness",
    "arm weakness":           "arm weakness",
    "slurring":               "slurred speech",
    "speech is slurred":      "slurred speech",
    "slurred speech":         "slurred speech",

    # fainting
    "passed out":             "syncope",
    "fainted":                "syncope",
    "blacked out":            "syncope",

    # rash
    "skin rash":              "rash",
    "red spots":              "rash",
    "hives":                  "rash",

    # eye
    "eye hurts":              "eye pain",
    "eyes hurt":              "eye pain",

    # swollen leg
    "leg is swollen":         "swollen leg",
    "swollen ankle":          "swollen leg",
    "leg swelling":           "swollen leg",
}

# All valid Neo4j Symptom node names
NEO4J_SYMPTOMS = set(SYNONYM_MAP.values()) | {
    "chest pain", "shortness of breath", "sweating", "sudden severe headache",
    "headache", "fever", "high fever", "sore throat", "runny nose", "body aches",
    "abdominal pain", "severe abdominal pain", "nausea", "vomiting blood",
    "black stool", "dizziness", "palpitations", "syncope", "cough", "rash",
    "swollen leg", "back pain", "difficulty swallowing", "eye pain",
    "facial drooping", "arm weakness", "slurred speech", "confusion",
}

_ner_pipeline = None


def load_biobert():
    global _ner_pipeline
    if _ner_pipeline is None:
        print("[NER] Loading BioBERT model...")
        model_name = "d4data/biomedical-ner-all"
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForTokenClassification.from_pretrained(model_name)
        _ner_pipeline = pipeline(
            "ner",
            model=model,
            tokenizer=tokenizer,
            aggregation_strategy="simple",
        )
        print("[NER] BioBERT loaded.")
    return _ner_pipeline


def _apply_synonym_map(text: str) -> list[str]:
    """Apply synonym map to raw text, longest match first."""
    text_lower = text.lower()
    found = []
    # Sort by length descending for longest match first
    for phrase, canonical in sorted(SYNONYM_MAP.items(), key=lambda x: -len(x[0])):
        if phrase in text_lower and canonical not in found:
            found.append(canonical)
    return found


def _biobert_extract(text: str) -> list[dict]:
    """Run BioBERT NER and return disease/symptom entities."""
    nlp = load_biobert()
    raw = nlp(text)
    entities = []
    for ent in raw:
        label = ent.get("entity_group", "")
        word = ent.get("word", "").strip().lower()
        score = round(float(ent.get("score", 0.0)), 3)
        if label in ("Disease_disorder", "Sign_symptom", "DISEASE", "SYMPTOM") and len(word) > 2:
            entities.append({"text": word, "label": label, "confidence": score})
    return entities


def _map_to_neo4j(raw_entities: list[dict]) -> list[dict]:
    """Map extracted entity text to Neo4j Symptom node names."""
    mapped = []
    seen = set()
    for ent in raw_entities:
        word = ent["text"].lower()
        # Direct match
        if word in NEO4J_SYMPTOMS and word not in seen:
            mapped.append({**ent, "neo4j_node": word, "label": "SYMPTOM"})
            seen.add(word)
            continue
        # Synonym match
        canonical = SYNONYM_MAP.get(word)
        if canonical and canonical not in seen:
            mapped.append({**ent, "text": canonical, "neo4j_node": canonical, "label": "SYMPTOM"})
            seen.add(canonical)
    return mapped


def extract_symptoms(text: str) -> dict:
    """
    Full pipeline:
    1. Synonym map pass (catches colloquial terms BioBERT may miss)
    2. BioBERT NER pass
    3. Map all results to Neo4j node IDs
    Returns structured result with symptoms + neo4j_nodes list.
    """
    # Pass 1: synonym map
    synonym_hits = _apply_synonym_map(text)

    # Pass 2: BioBERT
    biobert_entities = _biobert_extract(text)

    # Merge: synonym hits as high-confidence entities
    all_entities = [
        {"text": s, "label": "SYMPTOM", "confidence": 0.95, "source": "synonym_map"}
        for s in synonym_hits
    ]
    for ent in biobert_entities:
        all_entities.append({**ent, "source": "biobert"})

    # Map to Neo4j nodes
    mapped = _map_to_neo4j(all_entities)

    # Deduplicate neo4j nodes
    neo4j_nodes = list({e["neo4j_node"] for e in mapped})

    return {
        "input_text":    text,
        "entities":      mapped,
        "neo4j_nodes":   neo4j_nodes,
        "symptom_count": len(neo4j_nodes),
    }


if __name__ == "__main__":
    tests = [
        "My head has been throbbing all day and I feel hot",
        "I can't breathe properly and my chest is really tight",
        "I've been throwing up and feel dizzy",
        "My stomach hurts badly and I passed out earlier",
        "I have a runny nose, body aches and feel feverish",
    ]
    for t in tests:
        result = extract_symptoms(t)
        print(f"\nInput: {t}")
        print(f"Neo4j nodes: {result['neo4j_nodes']}")
