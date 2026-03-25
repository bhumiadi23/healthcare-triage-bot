"""
Live Demo Query — Chest Pain Node Connections
KPI: Run a live Cypher query showing node connections between
     'Chest Pain' and its associated risk factors.
Run: python demo_query.py
"""
from neo4j import GraphDatabase
from dotenv import load_dotenv
import os, ssl, certifi

load_dotenv()

URI  = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
AUTH = (os.getenv("NEO4J_USER",    "neo4j"),
        os.getenv("NEO4J_PASSWORD", "password"))


def run_demo(driver):
    with driver.session() as s:

        print("\n" + "="*60)
        print("  DEMO: Chest Pain — Neo4j Node Connections")
        print("="*60)

        # 1. Diseases linked to chest pain
        print("\n[1] Diseases indicated by 'chest pain':\n")
        r1 = s.run("""
            MATCH (sym:Symptom {name: 'chest pain'})-[r:INDICATES]->(d:Disease)-[:HAS_URGENCY]->(u:UrgencyLevel)
            RETURN d.name AS disease, u.level AS urgency, r.weight AS confidence
            ORDER BY r.weight DESC
        """)
        for rec in r1:
            print(f"    {rec['disease']:<35} urgency={rec['urgency']:<10} confidence={rec['confidence']}")

        # 2. Risk factors
        print("\n[2] Risk factors for chest-pain diseases:\n")
        r2 = s.run("""
            MATCH (sym:Symptom {name: 'chest pain'})-[:INDICATES]->(d:Disease)-[:HAS_RISK_FACTOR]->(rf:RiskFactor)
            RETURN d.name AS disease, rf.name AS risk_factor, rf.type AS type
            ORDER BY d.name
        """)
        for rec in r2:
            print(f"    {rec['disease']:<35} risk={rec['risk_factor']:<25} type={rec['type']}")

        # 3. Co-occurring diseases
        print("\n[3] Co-occurring diseases:\n")
        r3 = s.run("""
            MATCH (sym:Symptom {name: 'chest pain'})-[:INDICATES]->(d:Disease)-[:CO_OCCURS_WITH]->(d2:Disease)
            RETURN d.name AS disease, d2.name AS co_occurs_with
        """)
        rows = list(r3)
        if rows:
            for rec in rows:
                print(f"    {rec['disease']} --CO_OCCURS_WITH--> {rec['co_occurs_with']}")
        else:
            print("    (none in current graph)")

        # 4. Multi-symptom triage query
        print("\n[4] Multi-symptom query: ['chest pain', 'sweating', 'shortness of breath']\n")
        r4 = s.run("""
            MATCH (s:Symptom)-[r:INDICATES]->(d:Disease)-[:HAS_URGENCY]->(u:UrgencyLevel)
            WHERE toLower(s.name) IN ['chest pain', 'sweating', 'shortness of breath']
            WITH d, u, SUM(r.weight) AS match_score, COLLECT(s.name) AS matched
            ORDER BY match_score DESC
            RETURN d.name AS disease, u.level AS urgency, match_score, matched
            LIMIT 5
        """)
        for rec in r4:
            print(f"    {rec['disease']:<35} urgency={rec['urgency']:<10} score={rec['match_score']:.2f}  matched={rec['matched']}")

        print("\n" + "="*60)
        print("  [PASS] Live demo complete — Neo4j graph is working!")
        print("="*60 + "\n")


if __name__ == "__main__":
    ssl_ctx = ssl.create_default_context(cafile=certifi.where())
    driver = GraphDatabase.driver(URI, auth=AUTH, ssl_context=ssl_ctx)
    run_demo(driver)
    driver.close()
