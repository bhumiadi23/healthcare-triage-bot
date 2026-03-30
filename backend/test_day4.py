import requests
import json
import time

BASE_URL = "http://localhost:8000"

def print_separator():
    print("\n" + "="*60 + "\n")

def run_test_scenario(scenario_name, messages):
    print_separator()
    print(f"🩺 RUNNING TEST SCENARIO: {scenario_name}")
    print_separator()
    
    session_id = None
    
    for msg in messages:
        print(f"👤 USER:  {msg}")
        
        payload = {
            "user_input": msg,
            "patient_info": {"age": 45, "sex": "M"}
        }
        if session_id:
            payload["session_id"] = session_id
            
        try:
            response = requests.post(f"{BASE_URL}/chat", json=payload)
            response.raise_for_status()
            data = response.json()
            
            # Save session for multi-turn conversation
            session_id = data.get("session_id")
            
            print(f"🤖 BOT:   {data.get('reply')}")
            
            if data.get("triage"):
                print("\n🚨 FINAL TRIAGE RESULT PRODUCED:")
                print(json.dumps(data["triage"], indent=2))
                
            time.sleep(1) # Small pause for readability
            
            if data.get("triage"):
                break # Triage is final, end scenario
                
        except requests.exceptions.ConnectionError:
            print("❌ ERROR: Connection refused. Is the FastAPI server running?")
            return
        except Exception as e:
            print(f"❌ ERROR: {e}")
            if 'response' in locals():
                print(response.text)
            return

if __name__ == "__main__":
    print(f"Starting Day 4 Pipeline Tests against {BASE_URL}...")
    
    # ---------------------------------------------------------
    # Scenario 1: Red-Flag Rule Trigger (Instant Critical)
    # Testing that "chest pain" + "shortness of breath" immediately
    # triggers a Level 1 emergency without asking 15 questions.
    # ---------------------------------------------------------
    run_test_scenario(
        "Red-Flag Critical Scenario",
        [
            "My chest hurts really bad.",
            "I'm also having severe shortness of breath."
        ]
    )

    # ---------------------------------------------------------
    # Scenario 2: Guided Conversation Loop (Follow-up Questioning)
    # Testing the differential diagnosis where it needs more input.
    # ---------------------------------------------------------
    run_test_scenario(
        "Guided Conversation (Differential Diagnosis)",
        [
            "I have an itchy rash on my arm.",
            "No, I don't have a fever.",
            "It started completely gradually over a few days.",
            "No prior medical conditions."
        ]
    )

    # ---------------------------------------------------------
    # Scenario 3: Gibberish / Clarification Net
    # Testing stability when the user inputs something with no symptoms.
    # ---------------------------------------------------------
    run_test_scenario(
        "Gibberish / Clarification Net",
        [
            "Hello, I don't know what to do.",
            "Well today has just been a heavy, bad day.",
            "I have a really bad headache that won't go away."
        ]
    )
