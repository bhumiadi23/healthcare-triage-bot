"""
NER Accuracy Evaluation — NCBI Disease + BC5CDR Dataset
Runs extract_symptoms() against curated biomedical sentences.
Computes precision, recall, F1 per sample + overall.
Run: python ncbi_eval.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from ner import extract_symptoms, _apply_synonym_map
from dataset_samples import ALL_SAMPLES, NCBI_SAMPLES, BC5CDR_SAMPLES


# ── Synonym expansions for disease names (not in Neo4j but in ground truth) ──
DISEASE_SYNONYMS = {
    "meningitis":              ["meningitis", "bacterial meningitis"],
    "stroke":                  ["stroke", "cerebrovascular accident"],
    "appendicitis":            ["appendicitis", "acute appendicitis"],
    "pneumonia":               ["pneumonia", "community-acquired pneumonia"],
    "hypoglycemia":            ["hypoglycemia", "low blood sugar"],
    "glaucoma":                ["glaucoma", "acute angle-closure glaucoma"],
    "pulmonary embolism":      ["pulmonary embolism", "pe"],
    "deep vein thrombosis":    ["deep vein thrombosis", "dvt"],
    "cardiac arrhythmia":      ["cardiac arrhythmia", "arrhythmia"],
    "subarachnoid hemorrhage": ["subarachnoid hemorrhage", "sah"],
    "gastrointestinal bleed":  ["gastrointestinal bleed", "gi bleed", "gi bleeding"],
    "epiglottitis":            ["epiglottitis"],
    "nephrolithiasis":         ["nephrolithiasis", "kidney stone"],
    "meningococcal disease":   ["meningococcemia", "meningococcal disease"],
    "neurodegeneration":       ["neurodegeneration"],
    "huntington disease":      ["huntington disease", "huntington's disease"],
    "ruptured aortic aneurysm":["ruptured aortic aneurysm"],
}


def normalize(text: str) -> str:
    return text.lower().strip()


def entity_match(predicted: set, expected: set) -> tuple[int, int, int]:
    """Returns (true_positives, false_positives, false_negatives)"""
    # Expand expected with synonyms
    expanded_expected = set()
    for e in expected:
        expanded_expected.add(normalize(e))
        for synonyms in DISEASE_SYNONYMS.values():
            if normalize(e) in synonyms:
                expanded_expected.update(synonyms)

    tp = len(predicted & expanded_expected)
    fp = len(predicted - expanded_expected)
    fn = len(expanded_expected - predicted)
    return tp, fp, fn


def evaluate(samples: list[dict], label: str) -> dict:
    total_tp = total_fp = total_fn = 0
    results = []

    for sample in samples:
        result     = extract_symptoms(sample["text"])
        predicted  = {normalize(n) for n in result["neo4j_nodes"]}
        expected   = {normalize(e) for e in sample["expected_entities"]}

        tp, fp, fn = entity_match(predicted, expected)
        total_tp  += tp
        total_fp  += fp
        total_fn  += fn

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1        = (2 * precision * recall / (precision + recall)
                     if (precision + recall) > 0 else 0.0)

        results.append({
            "id":        sample["id"],
            "source":    sample["source"],
            "text":      sample["text"],
            "expected":  sorted(expected),
            "predicted": sorted(predicted),
            "tp": tp, "fp": fp, "fn": fn,
            "precision": round(precision, 2),
            "recall":    round(recall, 2),
            "f1":        round(f1, 2),
        })

    # Overall metrics
    overall_precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    overall_recall    = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    overall_f1        = (2 * overall_precision * overall_recall /
                         (overall_precision + overall_recall)
                         if (overall_precision + overall_recall) > 0 else 0.0)

    return {
        "label":     label,
        "samples":   len(samples),
        "results":   results,
        "overall": {
            "precision": round(overall_precision, 3),
            "recall":    round(overall_recall, 3),
            "f1":        round(overall_f1, 3),
            "tp": total_tp, "fp": total_fp, "fn": total_fn,
        },
    }


def print_report(eval_result: dict):
    label   = eval_result["label"]
    overall = eval_result["overall"]

    print(f"\n{'='*70}")
    print(f"  Dataset: {label}  ({eval_result['samples']} samples)")
    print(f"{'='*70}")
    print(f"  {'ID':<12} {'P':>5} {'R':>5} {'F1':>5}  {'Expected vs Predicted'}")
    print(f"  {'-'*66}".encode('ascii','replace').decode())

    for r in eval_result["results"]:
        match_icon = "[OK]  " if r["f1"] >= 0.5 else "[MISS]"
        print(f"  {match_icon} {r['id']:<10} P={r['precision']:.2f} R={r['recall']:.2f} F1={r['f1']:.2f}")
        print(f"         Expected : {r['expected']}")
        print(f"         Predicted: {r['predicted']}")
        if r["fn"] > 0:
            missing = set(r["expected"]) - set(r["predicted"])
            print(f"         Missing  : {sorted(missing)}")
        print()

    print(f"  {'='*66}")
    print(f"  OVERALL  Precision={overall['precision']:.3f}  "
          f"Recall={overall['recall']:.3f}  F1={overall['f1']:.3f}")
    print(f"           TP={overall['tp']}  FP={overall['fp']}  FN={overall['fn']}")
    print(f"{'='*70}")


def run_full_evaluation():
    print("\n" + "="*70)
    print("  BioBERT NER Evaluation — NCBI Disease + BC5CDR")
    print("  Pipeline: Synonym Map + BioBERT (d4data/biomedical-ner-all)")
    print("="*70)

    ncbi_eval   = evaluate(NCBI_SAMPLES,   "NCBI Disease Corpus")
    bc5cdr_eval = evaluate(BC5CDR_SAMPLES, "BC5CDR Corpus")
    all_eval    = evaluate(ALL_SAMPLES,    "Combined (NCBI + BC5CDR)")

    print_report(ncbi_eval)
    print_report(bc5cdr_eval)

    # Final combined summary table
    print(f"\n{'='*70}")
    print("  FINAL SUMMARY")
    print(f"{'='*70}")
    print(f"  {'Dataset':<25} {'Precision':>10} {'Recall':>8} {'F1':>8}")
    print(f"  {'-'*55}")
    for ev in [ncbi_eval, bc5cdr_eval, all_eval]:
        o = ev["overall"]
        print(f"  {ev['label']:<25} {o['precision']:>10.3f} {o['recall']:>8.3f} {o['f1']:>8.3f}")
    print(f"{'='*70}\n")

    return all_eval["overall"]["f1"]


if __name__ == "__main__":
    f1 = run_full_evaluation()
    print(f"[RESULT] Overall F1 Score: {f1:.3f}")
    if f1 >= 0.70:
        print("[PASS] NER accuracy meets the 70% F1 threshold for MVP.")
    else:
        print("[WARN] F1 below 0.70 — review synonym map coverage.")
