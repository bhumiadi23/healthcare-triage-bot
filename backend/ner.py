"""
Medical NER Pipeline — BioBERT + Synonym Map
Extracts standardized symptoms from free-text user input.
Maps conversational phrases to Neo4j Symptom node names.
"""
import logging
from transformers import pipeline, AutoTokenizer, AutoModelForTokenClassification

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("NER")

# ── Synonym map: conversational → Neo4j Symptom node name ────────────────────
SYNONYM_MAP = {
    # fever
    "hot":                     "fever",
    "burning up":              "fever",
    "temperature":             "fever",
    "running a fever":         "fever",
    "feeling feverish":        "fever",
    "feverish":                "fever",
    "high temperature":        "high fever",
    "chills":                  "high fever",

    # fatigue / weakness
    "weak":                    "fatigue",
    "weakness":                "fatigue",
    "tired":                   "fatigue",
    "exhausted":               "fatigue",
    "fatigue":                 "fatigue",
    "no energy":               "fatigue",
    "lethargic":               "fatigue",
    "feeling weak":            "fatigue",
    "feel weak":               "fatigue",

    # headache
    "throbbing":               "headache",
    "throbbing head":          "headache",
    "head hurts":              "headache",
    "head is pounding":        "headache",
    "pounding head":           "headache",
    "head pain":               "headache",
    "migraine":                "headache",

    # chest pain
    "chest hurts":             "chest pain",
    "chest tightness":         "chest pain",
    "tight chest":             "chest pain",
    "pressure in chest":       "chest pain",
    "chest pressure":          "chest pain",
    "chest pain":              "chest pain",
    "heart pain":              "chest pain",
    "diaphoresis":             "sweating",
    "diaphoretic":             "sweating",

    # breathing
    "can't breathe":           "shortness of breath",
    "cannot breathe":          "shortness of breath",
    "hard to breathe":         "shortness of breath",
    "trouble breathing":       "shortness of breath",
    "breathless":              "shortness of breath",
    "out of breath":           "shortness of breath",

    # nausea
    "feel sick":               "nausea",
    "feeling sick":            "nausea",
    "queasy":                  "nausea",
    "throwing up":             "nausea",
    "vomiting":                "nausea",
    "threw up":                "nausea",

    # dizziness
    "dizzy":                   "dizziness",
    "lightheaded":             "dizziness",
    "light headed":            "dizziness",
    "spinning":                "dizziness",

    # cough
    "coughing":                "cough",
    "dry cough":               "cough",
    "keep coughing":           "cough",

    # sore throat
    "throat hurts":            "sore throat",
    "scratchy throat":         "sore throat",

    # abdominal pain
    "stomach pain":            "abdominal pain",
    "stomach hurts":           "abdominal pain",
    "belly pain":              "abdominal pain",
    "stomach ache":            "abdominal pain",
    "tummy ache":              "abdominal pain",
    "cramping":                "abdominal pain",

    # sweating
    "sweaty":                  "sweating",
    "drenched in sweat":       "sweating",
    "night sweats":            "sweating",

    # body aches
    "body hurts":              "body aches",
    "everything hurts":        "body aches",
    "muscle pain":             "body aches",
    "achy":                    "body aches",

    # palpitations
    "heart racing":            "palpitations",
    "heart is racing":         "palpitations",
    "heart pounding":          "palpitations",
    "fast heartbeat":          "palpitations",

    # stroke
    "face drooping":           "facial drooping",
    "face is drooping":        "facial drooping",
    "arm is weak":             "arm weakness",
    "weak arm":                "arm weakness",
    "slurring":                "slurred speech",

    # fainting
    "passed out":              "syncope",
    "fainted":                 "syncope",
    "blacked out":             "syncope",

    # rash
    "skin rash":               "rash",
    "red spots":               "rash",
    "hives":                   "rash",

    # runny nose
    "nose is running":         "runny nose",
    "stuffy nose":             "runny nose",

    # back pain
    "back hurts":              "back pain",
    "lower back pain":         "back pain",

    # swollen leg
    "leg is swollen":          "swollen leg",
    "swollen ankle":           "swollen leg",
    "leg swelling":            "swollen leg",
}

NEO4J_SYMPTOMS = set(SYNONYM_MAP.values()) | {
    "chest pain", "shortness of breath", "sweating", "sudden severe headache",
    "headache", "fever", "high fever", "sore throat", "runny nose", "body aches",
    "abdominal pain", "severe abdominal pain", "nausea", "vomiting blood",
    "black stool", "dizziness", "palpitations", "syncope", "cough", "rash",
    "swollen leg", "back pain", "difficulty swallowing", "eye pain",
    "facial drooping", "arm weakness", "slurred speech", "confusion", "fatigue",
}

_ner_pipeline = None


def load_biobert():
    global _ner_pipeline
    if _ner_pipeline is None:
        log.info("Loading BioBERT model (d4data/biomedical-ner-all)...")
        model_name = "d4data/biomedical-ner-all"
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForTokenClassification.from_pretrained(model_name)
        _ner_pipeline = pipeline(
            "ner",
            model=model,
            tokenizer=tokenizer,
            aggregation_strategy="simple",
        )
        log.info("BioBERT loaded successfully.")
    return _ner_pipeline


def _synonym_pass(text: str) -> list[dict]:
    """Longest-match synonym scan over input text."""
    text_lower = text.lower()
    found = []
    seen = set()
    for phrase, canonical in sorted(SYNONYM_MAP.items(), key=lambda x: -len(x[0])):
        if phrase in text_lower and canonical not in seen:
            found.append({"text": canonical, "label": "SYMPTOM", "confidence": 0.95, "source": "synonym_map", "neo4j_node": canonical})
            seen.add(canonical)
    log.info(f"Synonym pass found: {[f['neo4j_node'] for f in found]}")
    return found


def _biobert_pass(text: str) -> list[dict]:
    """Run BioBERT NER with fallback on failure."""
    try:
        nlp = load_biobert()
        raw = nlp(text)
        log.info(f"BioBERT raw output: {raw}")
        entities = []
        for ent in raw:
            label = ent.get("entity_group", "")
            word = ent.get("word", "").strip().lower()
            score = round(float(ent.get("score", 0.0)), 3)
            if label in ("Disease_disorder", "Sign_symptom", "DISEASE", "SYMPTOM") and len(word) > 2:
                entities.append({"text": word, "label": label, "confidence": score, "source": "biobert"})
        log.info(f"BioBERT entities: {[e['text'] for e in entities]}")
        return entities
    except Exception as e:
        log.warning(f"BioBERT failed, using synonym map only. Error: {e}")
        return []


def _map_to_neo4j(entities: list[dict]) -> list[dict]:
    """Map entity text to Neo4j Symptom node names."""
    mapped = []
    seen = set()
    for ent in entities:
        word = ent["text"].lower()
        if "neo4j_node" in ent and ent["neo4j_node"] not in seen:
            mapped.append(ent)
            seen.add(ent["neo4j_node"])
            continue
        if word in NEO4J_SYMPTOMS and word not in seen:
            mapped.append({**ent, "neo4j_node": word})
            seen.add(word)
            continue
        canonical = SYNONYM_MAP.get(word)
        if canonical and canonical not in seen:
            mapped.append({**ent, "text": canonical, "neo4j_node": canonical})
            seen.add(canonical)
    return mapped


def extract_symptoms(text: str) -> dict:
    """
    Full pipeline:
    1. Synonym map pass (colloquial terms)
    2. BioBERT NER pass (clinical/medical terms)
    3. Merge + map to Neo4j node IDs
    """
    log.info(f"Processing: '{text}'")

    synonym_hits = _synonym_pass(text)
    biobert_hits = _biobert_pass(text)

    all_entities = synonym_hits + [
        {**e, "neo4j_node": None} for e in biobert_hits
    ]

    mapped = _map_to_neo4j(all_entities)
    mapped = [e for e in mapped if e.get("neo4j_node")]  # filter out unmatched
    neo4j_nodes = list({e["neo4j_node"] for e in mapped})

    log.info(f"Final Neo4j nodes: {neo4j_nodes}")

    return {
        "input_text":    text,
        "entities":      mapped,
        "neo4j_nodes":   neo4j_nodes,
        "symptom_count": len(neo4j_nodes),
    }
