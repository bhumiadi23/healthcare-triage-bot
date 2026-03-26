"""
NER Test Suite — Poor Description + Colloquial Input Test Cases
Proves BioBERT + synonym map extracts correct entities even from messy input.
Run: python test_ner.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from ner import extract_symptoms

# ── Test cases ────────────────────────────────────────────────────────────────
# Format: (description, input_text, expected_neo4j_nodes)
TEST_CASES = [

    # --- Synonym mapping tests ---
    (
        "Colloquial: 'hot' -> fever, 'throbbing head' -> headache",
        "My head has been throbbing all day and I feel really hot",
        ["headache", "fever"],
    ),
    (
        "Colloquial: 'tight chest' -> chest pain, 'can't breathe' -> shortness of breath",
        "I have a tight chest and I just can't breathe properly",
        ["chest pain", "shortness of breath"],
    ),
    (
        "Colloquial: 'dizzy' -> dizziness, 'throwing up' -> nausea",
        "I've been really dizzy and keep throwing up since this morning",
        ["dizziness", "nausea"],
    ),
    (
        "Colloquial: 'passed out' -> syncope, 'stomach hurts' -> abdominal pain",
        "My stomach hurts so bad and I passed out for a few seconds",
        ["abdominal pain", "syncope"],
    ),
    (
        "Colloquial: 'heart racing' -> palpitations, 'sweaty' -> sweating",
        "My heart is racing and I am completely sweaty",
        ["palpitations", "sweating"],
    ),

    # --- Filler-heavy inputs ---
    (
        "Filler-heavy: should still extract fever + headache",
        "I don't know what's wrong but I just feel really hot and my head is pounding",
        ["fever", "headache"],
    ),
    (
        "Filler-heavy: vague complaint with hidden symptoms",
        "I feel terrible, like everything hurts and I have a runny nose and keep coughing",
        ["body aches", "runny nose", "cough"],
    ),
    (
        "Filler-heavy: emotional language masking stroke symptoms",
        "Something is really wrong, my face is drooping on one side and my arm is weak",
        ["facial drooping", "arm weakness"],
    ),

    # --- Poor medical vocabulary ---
    (
        "Poor vocab: 'diaphoresis' -> sweating (medical synonym)",
        "History of chest pain radiating to the left arm with diaphoresis",
        ["chest pain", "sweating"],
    ),
    (
        "Poor vocab: 'dyspnea' -> shortness of breath",
        "Patient presents with fever, cough, and dyspnea",
        ["fever", "cough", "shortness of breath"],
    ),
    (
        "Poor vocab: 'blacked out' -> syncope",
        "I blacked out in the bathroom and hit my head",
        ["syncope"],
    ),
    (
        "Poor vocab: 'burning up' -> fever, 'queasy' -> nausea",
        "I'm burning up and feeling really queasy",
        ["fever", "nausea"],
    ),

    # --- Multi-symptom complex inputs ---
    (
        "Multi-symptom: stroke triad",
        "Facial drooping, arm weakness, and slurred speech started suddenly",
        ["facial drooping", "arm weakness", "slurred speech"],
    ),
    (
        "Multi-symptom: cardiac event",
        "Chest pain, sweating, and shortness of breath for the last 20 minutes",
        ["chest pain", "sweating", "shortness of breath"],
    ),
    (
        "Multi-symptom: flu-like illness",
        "I have a runny nose, body aches, sore throat and feel feverish",
        ["runny nose", "body aches", "sore throat", "fever"],
    ),
]


def run_tests():
    passed = failed = 0

    print("\n" + "="*70)
    print("  BioBERT NER — Poor Description Test Suite")
    print("  Tests: synonym mapping, filler removal, poor vocabulary")
    print("="*70)

    for i, (desc, text, expected) in enumerate(TEST_CASES, 1):
        result       = extract_symptoms(text)
        predicted    = set(result["neo4j_nodes"])
        expected_set = set(expected)
        ok           = expected_set.issubset(predicted)

        if ok:
            passed += 1
            status = "PASS"
        else:
            failed += 1
            status = "FAIL"

        print(f"\n[{i:02d}] {status} — {desc}")
        print(f"      Input    : {text}")
        print(f"      Expected : {sorted(expected_set)}")
        print(f"      Got      : {sorted(predicted)}")
        if not ok:
            missing = expected_set - predicted
            extra   = predicted - expected_set
            if missing:
                print(f"      Missing  : {sorted(missing)}")
            if extra:
                print(f"      Extra    : {sorted(extra)}")

    accuracy = passed / len(TEST_CASES) * 100
    print("\n" + "="*70)
    print(f"  Results : {passed}/{len(TEST_CASES)} passed  ({accuracy:.1f}% accuracy)")
    print(f"  Status  : {'[PASS] Meets MVP threshold' if accuracy >= 70 else '[FAIL] Below 70% threshold'}")
    print("="*70 + "\n")

    return passed, failed


if __name__ == "__main__":
    run_tests()
