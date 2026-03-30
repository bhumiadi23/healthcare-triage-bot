"""
Guided Conversation Engine — Day 4
State machine for multi-turn triage: tracks asked questions,
selects discriminating follow-ups, and builds legally safe responses.
Max 15 questions per session.
"""
import logging

log = logging.getLogger("CONVERSATION")

MAX_QUESTIONS = 15

# ── Discriminating questions keyed by disease name ───────────────────────────
# Used when Neo4j returns multiple candidate diseases.
_DISC_QUESTIONS: dict[str, list[str]] = {
    "Myocardial Infarction": [
        "Does the chest pain radiate to your left arm, jaw, or shoulder?",
        "Did the pain start suddenly at rest rather than during exertion?",
        "Are you sweating or feeling nauseous along with the chest pain?",
    ],
    "Angina": [
        "Does the chest discomfort come on with physical activity and go away with rest?",
        "Have you been diagnosed with coronary artery disease before?",
    ],
    "Stroke": [
        "Did the weakness or facial drooping start suddenly within the last few hours?",
        "Is the weakness or numbness on one side of your body only?",
        "Do you have any difficulty understanding what others are saying?",
    ],
    "TIA": [
        "Did the symptoms resolve completely within a few minutes to an hour?",
        "Have you had similar brief episodes before?",
    ],
    "Pulmonary Embolism": [
        "Do you have any swelling, redness, or pain in one of your legs?",
        "Have you recently had surgery, a long flight, or been immobile for a long time?",
        "Is the breathing difficulty worse when you take a deep breath?",
    ],
    "Asthma Attack": [
        "Do you hear a wheezing or whistling sound when you breathe?",
        "Do you have a known history of asthma or allergies?",
        "Did the breathing difficulty start after exposure to dust, smoke, or an allergen?",
    ],
    "Meningitis": [
        "Do you have a stiff neck that makes it hard to touch your chin to your chest?",
        "Are you sensitive to bright light or loud sounds right now?",
        "Do you have a rash anywhere on your body?",
    ],
    "Sepsis": [
        "Do you have a known infection, wound, or recent surgical procedure?",
        "Are you feeling confused or unusually drowsy?",
        "Is your skin pale, mottled, or unusually cold to the touch?",
    ],
    "Appendicitis": [
        "Is the pain concentrated on the lower right side of your abdomen?",
        "Does the pain get worse when you move, cough, or press on your stomach?",
        "Do you have a loss of appetite along with the abdominal pain?",
    ],
    "Gastroenteritis": [
        "Do you have diarrhea along with the abdominal pain?",
        "Have you recently eaten food that might have been undercooked or spoiled?",
        "Are others around you experiencing similar symptoms?",
    ],
    "Migraine": [
        "Is the headache on one side of your head?",
        "Are you sensitive to light or sound right now?",
        "Do you have any nausea or visual disturbances like zigzag lines?",
    ],
    "Tension Headache": [
        "Does the headache feel like a tight band or pressure around your head?",
        "Have you been under significant stress or had poor sleep recently?",
    ],
    "UTI": [
        "Do you have a burning sensation when urinating?",
        "Are you urinating more frequently than usual?",
        "Do you have any lower abdominal or pelvic discomfort?",
    ],
    "Kidney Stone": [
        "Is the pain sharp and coming in waves on your side or back?",
        "Does the pain radiate down toward your groin?",
        "Have you noticed any blood in your urine?",
    ],
    "Vertigo": [
        "Does the room feel like it is spinning around you?",
        "Does the dizziness get worse when you change head position?",
        "Have you had any recent ear infection or hearing changes?",
    ],
    "Hypoglycemia": [
        "When did you last eat? Have you skipped a meal?",
        "Do you have diabetes or take any blood sugar medications?",
        "Are you feeling shaky, sweaty, or confused along with the dizziness?",
    ],
    "Pneumonia": [
        "Do you have a productive cough with yellow or green mucus?",
        "Do you have a fever along with the cough?",
        "Is the cough accompanied by chest pain when you breathe deeply?",
    ],
    "COVID-19": [
        "Have you lost your sense of taste or smell recently?",
        "Have you been in contact with anyone who tested positive for COVID-19?",
        "Do you have fatigue and body aches along with the cough?",
    ],
}

# ── Generic follow-ups when no disease-specific question is available ─────────
_GENERIC_FOLLOWUPS = [
    "How long have you been experiencing these symptoms?",
    "On a scale of 1 to 10, how severe is your discomfort right now?",
    "Did the symptoms start suddenly or come on gradually?",
    "Do you have any known medical conditions such as diabetes or heart disease?",
    "Are you currently taking any medications?",
    "Do the symptoms get worse with physical activity?",
    "Have you had these symptoms before?",
    "Have you recently traveled or been exposed to anyone who was sick?",
    "Is there anything that makes the symptoms better or worse?",
    "What is your approximate age, and do you smoke or drink alcohol?",
]

# ── Clarification prompts for gibberish / no-symptom input ───────────────────
_CLARIFICATION_PROMPTS = [
    "I didn't detect any specific medical symptoms in that. Could you describe what you're physically feeling? For example: headache, chest pain, or fever.",
    "To help route you to the right care, I need to understand your symptoms. What part of your body is bothering you?",
    "I want to make sure I understand correctly. Could you describe your symptoms in more detail? For example: 'I have a headache and fever'.",
    "Could you please describe your symptoms more clearly? For example: 'I feel chest tightness and shortness of breath'.",
]


def get_next_question(
    top_diseases: list[str],
    asked_questions: list[str],
    turn: int,
) -> str | None:
    """
    Return the next follow-up question, or None if max questions reached.
    Priority: disease-specific discriminating question > generic follow-up.
    """
    if turn >= MAX_QUESTIONS:
        return None

    asked_set = set(asked_questions)

    # Disease-specific discriminating questions first
    for disease in top_diseases:
        for q in _DISC_QUESTIONS.get(disease, []):
            if q not in asked_set:
                return q

    # Fall back to generic questions
    for q in _GENERIC_FOLLOWUPS:
        if q not in asked_set:
            return q

    return None


def get_clarification_prompt(asked_clarifications: list[str]) -> str:
    """Return an unused clarification prompt for gibberish/no-symptom input."""
    asked_set = set(asked_clarifications)
    for p in _CLARIFICATION_PROMPTS:
        if p not in asked_set:
            return p
    return "Could you please describe your symptoms more clearly?"


def build_safe_response(
    conditions: list[str],
    urgency: str,
    action: str,
    follow_up: str | None,
    is_final: bool,
) -> dict:
    """
    Build a legally safe, probabilistic response.
    Uses 'may be experiencing' language — never 'you have'.
    """
    top = " or ".join(conditions[:2]) if conditions else "an underlying condition"

    if urgency == "CRITICAL":
        message = (
            f"Based on your symptoms, this appears to be a medical emergency. "
            f"You may be experiencing {top}. {action}."
        )
    elif urgency == "HIGH":
        message = (
            f"Your symptoms suggest you may be experiencing {top}. "
            f"This requires prompt medical attention. {action}."
        )
    elif urgency == "MEDIUM":
        message = (
            f"You may be experiencing {top}. "
            f"It is advisable to seek medical care soon. {action}."
        )
    else:
        message = (
            f"Your symptoms may indicate {top}. "
            f"Consider consulting a healthcare professional. {action}."
        )

    response: dict = {
        "message":       message,
        "urgency_level": urgency,
        "action":        action,
        "conditions":    conditions,
        "is_final":      is_final,
        "disclaimer":    (
            "This is not a medical diagnosis. "
            "Always consult a qualified healthcare professional."
        ),
    }

    if follow_up and not is_final:
        response["follow_up_question"] = follow_up

    return response


def should_finalize(turn: int, urgency: str, symptoms_count: int) -> bool:
    """Decide whether to finalize triage or continue asking questions."""
    if urgency == "CRITICAL":
        return True               # Always finalize immediately on CRITICAL
    if turn >= MAX_QUESTIONS:
        return True               # Hard cap
    if turn >= 3 and symptoms_count >= 3:
        return True               # Enough data collected
    return False
