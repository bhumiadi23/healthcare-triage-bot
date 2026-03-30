"""
test_pdf.py — Quick smoke test for the Doctor Handoff Report endpoint.

Usage:
    python test_pdf.py

Requires the backend to be running on http://localhost:8000.
"""

import json
import requests

BASE = "http://localhost:8000"
SESSION_ID = "DEMO-SARAH-2026-0042"

DEMO_MESSAGES = [
    "I have chest tightness and shortness of breath for the past 2 hours",
    "Yes, the pain radiates to my left arm and I'm sweating heavily",
    "My name is Sarah Johnson, I'm 46. I have hypertension and diabetes.",
]


def run_chat(session_id, messages):
    """Drive a full triage conversation and return the last response."""
    sid = session_id
    last = {}
    for msg in messages:
        r = requests.post(f"{BASE}/chat", json={
            "session_id": sid,
            "user_input": msg,
            "patient_info": {
                "name": "Sarah Johnson",
                "age": 46,
                "known_conditions": ["Hypertension", "Type 2 Diabetes"]
            }
        }, timeout=30)
        r.raise_for_status()
        last = r.json()
        sid = last.get("session_id", sid)
        print(f"[TURN] User: {msg[:60]}...")
        print(f"       Bot:  {last.get('reply', '')[:80]}...")
        print()
    return sid, last


def run_report(session_id):
    """Generate the Doctor Handoff Report for the session."""
    r = requests.post(f"{BASE}/report", json={"session_id": session_id}, timeout=30)
    r.raise_for_status()
    return r.json()


def main():
    print("=" * 60)
    print("  MedTriage AI — Doctor Handoff Report Smoke Test")
    print("=" * 60)

    # Health check
    try:
        h = requests.get(f"{BASE}/health", timeout=5)
        print(f"✓ Backend health: {h.json()}\n")
    except Exception as e:
        print(f"✗ Backend not reachable: {e}")
        print("  Start it with:  uvicorn main:app --reload --port 8000")
        return

    # Chat flow
    print("── Running triage chat flow ──")
    session_id, last_response = run_chat(SESSION_ID, DEMO_MESSAGES)

    triage = last_response.get("triage") or {}
    print(f"✓ Triage level  : {triage.get('urgency_level', 'N/A')}")
    print(f"✓ Urgency score : {triage.get('urgency_score', 'N/A')}")
    print(f"✓ Conditions    : {', '.join(triage.get('possible_conditions', []))}")
    print()

    # Generate report
    print("── Generating Doctor Handoff Report ──")
    try:
        report = run_report(session_id)
        print(f"✓ Report ID     : {report.get('report_id')}")
        print(f"✓ Session ID    : {report.get('session_id')}")
        print(f"✓ Symptoms      : {[s['symptom'] for s in report.get('extracted_symptoms', [])]}")
        print(f"✓ Differential  : {[d['condition'] for d in report.get('differential_diagnosis', [])]}")
        print(f"✓ Timeline items: {len(report.get('conversation_timeline', []))}")
        print(f"✓ Vital flags   : {len(report.get('vital_flags', []))}")
        print()
        print("── Full Report (JSON) ──")
        print(json.dumps(report, indent=2, default=str))
    except requests.HTTPError as e:
        print(f"✗ Report generation failed: {e}")
        print(f"  Response: {e.response.text}")

    print("\n✅ Test complete.")


if __name__ == "__main__":
    main()
