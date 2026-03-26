"""
Master Evaluation Runner
Runs: (1) Poor-description test suite  (2) NCBI + BC5CDR dataset evaluation
Run: python run_eval.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from test_ner  import run_tests
from ncbi_eval import run_full_evaluation

if __name__ == "__main__":
    print("\n" + "#"*70)
    print("  STEP 1 — Poor Description Test Suite")
    print("#"*70)
    passed, failed = run_tests()

    print("\n" + "#"*70)
    print("  STEP 2 — NCBI Disease + BC5CDR Dataset Evaluation")
    print("#"*70)
    f1 = run_full_evaluation()

    print("\n" + "#"*70)
    print("  FINAL REPORT")
    print("#"*70)
    print(f"  Test Suite  : {passed}/{passed+failed} passed  ({passed/(passed+failed)*100:.1f}%)")
    print(f"  Dataset F1  : {f1:.3f}")
    print(f"  Architecture: Synonym Map -> BioBERT NER -> Neo4j Node Mapping")
    print(f"  Status      : {'[READY] Pipeline meets Day 3 KPIs' if f1 >= 0.6 else '[NEEDS WORK]'}")
    print("#"*70 + "\n")
