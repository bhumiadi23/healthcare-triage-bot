"""
NER Test Cases — Day 3
Tests BioBERT + synonym pipeline against messy conversational input.
Includes BC5CDR-style disease/symptom examples.
Run: python test_ner.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from ner import extract_symptoms

# ── Test cases ────────────────────────────────────────────────────────────────
# Format: (input_text, expected_neo4j_nodes)
TEST_CASES = [
    # Core Day 3 example
    (
        "My head has been throbbing all day and I feel hot",
        ["headache", "fever"],
    ),
    # Synonym: "tight chest" → chest pain, "can't breathe" → shortness of breath
    (
        "I have a tight chest and I can't breathe properly",
        ["chest pain", "shortness of breath"],
    ),
    # Synonym: "dizzy" → dizziness, "throwing up" → nausea
    (
        "I've been really dizzy and keep throwing up since morning",
        ["dizziness", "nausea"],
    ),
    # Synonym: "passed out" → syncope, "stomach hurts" → abdominal pain
    (
        "My stomach hurts so bad and I passed out for a few seconds",
        ["abdominal pain", "syncope"],
    ),
    # Synonym: "heart racing" → palpitations, "sweaty" → sweating
    (
        "My heart is racing and I'm completely sweaty",
        ["palpitations", "sweating"],
    ),
    # Stroke symptoms — colloquial
    (
        "My face is drooping on one side and my arm is weak",
        ["facial drooping", "arm weakness"],
    ),
    # BC5CDR-style: clinical text
    (
        "Patient presents with fever, cough, and shortness of breath",
        ["fever", "cough", "shortness of breath"],
    ),
    # BC5CDR-style: disease mention
    (
        "History of chest pain radiating to the left arm with diaphoresis",
        ["chest pain", "sweating"],
    ),
    # Filler-heavy input — should still extract
    (
        "I don't know what's wrong but I just feel really hot and my head is pounding",
        ["fever", "headache"],
    ),
    # Multi-symptom messy
    (
        "Everything hurts, I have a runny nose and I've been coughing all night",
        ["body aches", "runny nose", "cough"],
    ),
]


def run_tests():
    passed = 0
    failed = 0

    print("\n" + "="*65)
    print("  BioBERT NER — Test Suite")
    print("="*65)

    for i, (text, expected) in enumerate(TEST_CASES, 1):
        result = extract_symptoms(text)
        found = set(result["neo4j_nodes"])
        expected_set = set(expected)
        # Pass if all expected nodes are found
        ok = expected_set.issubset(found)

        status = "PASS" if ok else "FAIL"
        if ok:
            passed += 1
        else:
            failed += 1

        print(f"\n[{i}] {status}")
        print(f"     Input:    {text}")
        print(f"     Expected: {sorted(expected_set)}")
        print(f"     Got:      {sorted(found)}")
        if not ok:
            missing = expected_set - found
            print(f"     Missing:  {sorted(missing)}")

    print("\n" + "="*65)
    print(f"  Results: {passed}/{len(TEST_CASES)} passed")
    print("="*65 + "\n")
    return passed, failed


if __name__ == "__main__":
    run_tests()
