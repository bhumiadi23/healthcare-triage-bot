"""
Rule-Based Triage Classifier — Day 4
Hardcoded red-flag rules that guarantee life-threatening symptoms
are NEVER classified below CRITICAL/HIGH.

Tuning log is written to triage_debug.log on every startup so the
audit trail is always up-to-date.
"""
import logging

# ── Tuning / audit logger ─────────────────────────────────────────────────────
_tune_log = logging.getLogger("TRIAGE_TUNING")
if not _tune_log.handlers:
    _fh = logging.FileHandler("triage_debug.log")
    _fh.setFormatter(logging.Formatter("%(asctime)s  %(levelname)s  %(message)s"))
    _tune_log.addHandler(_fh)
    _tune_log.setLevel(logging.INFO)

# ── Red-flag rule table ───────────────────────────────────────────────────────
# Each entry: (frozenset of required symptoms, urgency, score, action, rationale)
# Rules are evaluated in order; first match wins.
RED_FLAG_RULES: list[tuple[frozenset, str, int, str, str]] = [
    # ── CRITICAL combos ──────────────────────────────────────────────────────
    (
        frozenset({"chest pain", "shortness of breath"}),
        "CRITICAL", 98, "Call 108 immediately",
        "Chest Pain + Shortness of Breath = Instant Level 1 Emergency (ACS/PE protocol)",
    ),
    (
        frozenset({"facial drooping", "arm weakness"}),
        "CRITICAL", 97, "Call 108 immediately — Stroke protocol",
        "FAST stroke criteria: Face + Arm = high-probability stroke",
    ),
    (
        frozenset({"facial drooping", "slurred speech"}),
        "CRITICAL", 97, "Call 108 immediately — Stroke protocol",
        "FAST stroke criteria: Face + Speech = high-probability stroke",
    ),
    (
        frozenset({"arm weakness", "slurred speech"}),
        "CRITICAL", 96, "Call 108 immediately — Stroke protocol",
        "FAST stroke criteria: Arm + Speech = high-probability stroke",
    ),
    (
        frozenset({"sudden severe headache", "neck stiffness"}),
        "CRITICAL", 97, "Call 108 immediately — Meningitis/SAH protocol",
        "Thunderclap headache + neck stiffness = subarachnoid hemorrhage or meningitis",
    ),
    (
        frozenset({"high fever", "neck stiffness"}),
        "CRITICAL", 96, "Call 108 immediately — Meningitis protocol",
        "Fever + neck stiffness = bacterial meningitis until proven otherwise",
    ),
    (
        frozenset({"high fever", "rash"}),
        "CRITICAL", 96, "Call 108 immediately — Septicemia protocol",
        "Fever + non-blanching rash = meningococcal septicemia",
    ),
    (
        frozenset({"chest pain", "sweating"}),
        "CRITICAL", 95, "Call 108 immediately — ACS protocol",
        "Chest pain + diaphoresis = classic MI presentation",
    ),
    (
        frozenset({"chest pain", "nausea"}),
        "CRITICAL", 94, "Call 108 immediately — ACS protocol",
        "Chest pain + nausea = atypical MI presentation",
    ),
    (
        frozenset({"shortness of breath", "swollen leg"}),
        "CRITICAL", 95, "Call 108 immediately — PE protocol",
        "Dyspnea + unilateral leg swelling = pulmonary embolism",
    ),
    (
        frozenset({"severe abdominal pain", "sweating"}),
        "CRITICAL", 95, "Call 108 immediately — Surgical emergency",
        "Severe abdominal pain + diaphoresis = ruptured aneurysm/peritonitis",
    ),
    (
        frozenset({"confusion", "high fever"}),
        "CRITICAL", 95, "Call 108 immediately — Sepsis protocol",
        "Altered mental status + fever = septic encephalopathy",
    ),
    (
        frozenset({"suicidal"}),
        "CRITICAL", 99, "Call 108 immediately — Psychiatric emergency",
        "Any suicidal ideation = immediate psychiatric emergency",
    ),
    (
        frozenset({"vomiting blood"}),
        "CRITICAL", 97, "Call 108 immediately — GI Bleed protocol",
        "Hematemesis = upper GI bleed, potentially life-threatening",
    ),
    (
        frozenset({"coughing up blood"}),
        "CRITICAL", 96, "Call 108 immediately — Hemoptysis protocol",
        "Hemoptysis = pulmonary embolism, TB, or malignancy",
    ),
    (
        frozenset({"black stool"}),
        "CRITICAL", 94, "Go to ER immediately — GI Bleed protocol",
        "Melena = upper GI bleed requiring urgent endoscopy",
    ),
    (
        frozenset({"syncope"}),
        "CRITICAL", 93, "Call 108 immediately — Cardiac protocol",
        "Unexplained syncope = cardiac arrhythmia until proven otherwise",
    ),
    (
        frozenset({"difficulty swallowing", "shortness of breath"}),
        "CRITICAL", 95, "Call 108 immediately — Airway emergency",
        "Dysphagia + dyspnea = epiglottitis/anaphylaxis airway threat",
    ),
    # ── Single-symptom CRITICAL overrides ────────────────────────────────────
    (
        frozenset({"sudden severe headache"}),
        "CRITICAL", 95, "Call 108 immediately — SAH protocol",
        "Thunderclap headache alone = subarachnoid hemorrhage until proven otherwise",
    ),
    (
        frozenset({"facial drooping"}),
        "CRITICAL", 97, "Call 108 immediately — Stroke protocol",
        "Facial drooping alone = stroke until proven otherwise",
    ),
    (
        frozenset({"slurred speech"}),
        "CRITICAL", 95, "Call 108 immediately — Stroke protocol",
        "Slurred speech alone = stroke until proven otherwise",
    ),
    # ── HIGH combos ──────────────────────────────────────────────────────────
    (
        frozenset({"chest pain"}),
        "HIGH", 80, "Go to ER now — Cardiac evaluation required",
        "Isolated chest pain = ACS must be ruled out in ER",
    ),
    (
        frozenset({"shortness of breath"}),
        "HIGH", 78, "Go to ER now — Respiratory evaluation required",
        "Isolated dyspnea = PE/asthma/cardiac cause must be excluded",
    ),
    (
        frozenset({"high fever", "confusion"}),
        "HIGH", 82, "Go to ER now — Sepsis screening",
        "Fever + confusion = sepsis screening required",
    ),
    (
        frozenset({"abdominal pain", "fever"}),
        "HIGH", 78, "Go to ER now — Appendicitis/peritonitis screening",
        "Abdominal pain + fever = surgical emergency must be excluded",
    ),
    (
        frozenset({"palpitations", "dizziness"}),
        "HIGH", 76, "Go to ER now — Arrhythmia evaluation",
        "Palpitations + dizziness = hemodynamically significant arrhythmia",
    ),
    (
        frozenset({"swollen leg", "back pain"}),
        "HIGH", 75, "Go to ER now — DVT/PE screening",
        "Leg swelling + back pain = DVT with possible PE",
    ),
]

# ── Startup: log every rule for audit trail ───────────────────────────────────
_tune_log.info("=" * 70)
_tune_log.info("RED-FLAG RULE TABLE LOADED — triage_debug.log audit trail")
_tune_log.info("=" * 70)
for _syms, _lvl, _score, _action, _rationale in RED_FLAG_RULES:
    _tune_log.info(
        f"RULE | {_lvl:8s} | score={_score} | symptoms={sorted(_syms)} | {_rationale}"
    )
_tune_log.info(f"Total rules loaded: {len(RED_FLAG_RULES)}")
_tune_log.info("GUARANTEE: No life-threatening symptom combination can produce LOW or MEDIUM via rule engine.")
_tune_log.info("=" * 70)


def check_red_flags(collected_symptoms: set) -> dict | None:
    """
    Evaluate all red-flag rules against the collected symptom set.
    Returns the highest-priority match, or None if no rule fires.
    Logs every trigger for the debugging audit trail.
    """
    normalised = {s.lower().strip() for s in collected_symptoms}
    best = None

    for rule_syms, urgency, score, action, rationale in RED_FLAG_RULES:
        if rule_syms.issubset(normalised):
            _tune_log.info(
                f"RED FLAG TRIGGERED | {urgency} | matched={sorted(rule_syms)} | {rationale}"
            )
            if best is None or score > best["urgency_score"]:
                best = {
                    "urgency_level":       urgency,
                    "urgency_score":       score,
                    "recommended_action":  action,
                    "possible_conditions": _conditions_for(rule_syms),
                    "source":              f"rule_engine ({rationale})",
                    "confidence":          0.99,
                    "rule_matched":        sorted(rule_syms),
                }

    if best:
        _tune_log.info(f"FINAL RULE RESULT: {best['urgency_level']} | {best['recommended_action']}")
    return best


# ── Internal helpers ──────────────────────────────────────────────────────────

_SYMPTOM_CONDITIONS: dict[str, list[str]] = {
    "chest pain":            ["Myocardial Infarction", "Angina", "Aortic Dissection"],
    "shortness of breath":   ["Pulmonary Embolism", "Asthma Attack", "Heart Failure"],
    "facial drooping":       ["Ischemic Stroke", "Hemorrhagic Stroke"],
    "arm weakness":          ["Ischemic Stroke", "TIA"],
    "slurred speech":        ["Ischemic Stroke", "TIA"],
    "sudden severe headache":["Subarachnoid Hemorrhage", "Meningitis"],
    "neck stiffness":        ["Meningitis", "Subarachnoid Hemorrhage"],
    "high fever":            ["Sepsis", "Meningitis"],
    "rash":                  ["Meningococcemia", "Septicemia"],
    "vomiting blood":        ["Upper GI Bleed", "Esophageal Varices"],
    "coughing up blood":     ["Pulmonary Embolism", "Tuberculosis"],
    "black stool":           ["Upper GI Bleed"],
    "syncope":               ["Cardiac Arrhythmia", "Vasovagal Syncope"],
    "swollen leg":           ["Deep Vein Thrombosis", "Pulmonary Embolism"],
    "severe abdominal pain": ["Ruptured Aortic Aneurysm", "Peritonitis"],
    "confusion":             ["Septic Encephalopathy", "Stroke"],
    "suicidal":              ["Psychiatric Emergency"],
    "palpitations":          ["Atrial Fibrillation", "Ventricular Tachycardia"],
    "abdominal pain":        ["Appendicitis", "Peritonitis"],
    "difficulty swallowing": ["Epiglottitis", "Anaphylaxis"],
}


def _conditions_for(symptoms: frozenset) -> list[str]:
    seen, result = set(), []
    for s in symptoms:
        for c in _SYMPTOM_CONDITIONS.get(s, []):
            if c not in seen:
                result.append(c)
                seen.add(c)
    return result or ["Critical Emergency"]
