"""
LLM / Algorithmic Engine — Day 4
Generates discriminating follow-up questions from Neo4j graph data
and builds legally safe probabilistic diagnosis strings.
"""
import logging

log = logging.getLogger("LLM_ENGINE")


async def generate_discriminating_question(
    neo4j_session,
    top_diseases: list[str],
    collected_symptoms: set,
) -> str:
    """
    Query Neo4j for the most discriminating symptom not yet collected,
    then return a natural-language follow-up question.
    Falls back to a generic question if Neo4j is unavailable.
    """
    if neo4j_session and top_diseases:
        try:
            query = """
                MATCH (s:Symptom)-[:INDICATES]->(d:Disease)
                WHERE d.name IN $diseases
                  AND NOT toLower(s.name) IN $collected
                WITH s.name AS sym, COUNT(DISTINCT d) AS freq
                ORDER BY freq DESC
                LIMIT 1
                RETURN sym
            """
            result = await neo4j_session.run(
                query,
                diseases=top_diseases,
                collected=[c.lower() for c in collected_symptoms],
            )
            records = await result.data()
            if records:
                sym = records[0]["sym"]
                log.info(f"Neo4j discriminating symptom: {sym}")
                return f"To help narrow this down — are you also experiencing any {sym}?"
        except Exception as e:
            log.warning(f"Neo4j discriminating query failed: {e}")

    # Fallback: ask about the most common differentiating factor
    if top_diseases:
        return (
            f"To help distinguish between {' and '.join(top_diseases[:2])}, "
            f"could you describe any additional symptoms you're noticing?"
        )
    return "Are there any other symptoms you've noticed?"


def build_safe_diagnosis(conditions: list[str]) -> str:
    """
    Return a legally safe, probabilistic diagnosis string.
    Uses 'may be experiencing' — never 'you have'.
    """
    top = " or ".join(conditions[:2]) if conditions else "an underlying condition"
    return (
        f"Based on your symptoms, you **may be experiencing** {top}. "
        f"Please consult a qualified healthcare professional for an official diagnosis. "
        f"This assessment is not a substitute for medical advice."
    )


def generate_clarification_prompt() -> str:
    """Return a safe clarification prompt for gibberish or unrecognised input."""
    return (
        "I'm sorry, I didn't detect any specific medical symptoms in that. "
        "Could you describe what you're physically feeling? "
        "For example: headache, chest pain, or shortness of breath."
    )
