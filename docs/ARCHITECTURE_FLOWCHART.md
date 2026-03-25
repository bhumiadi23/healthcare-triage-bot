# System Architecture Flowchart
# Render at: https://mermaid.live

```mermaid
flowchart TD
    A([👤 Patient]) -->|Types symptoms in free-text| B[React Chat UI]

    B -->|POST /chat - raw text| C[FastAPI Backend]

    C -->|text| D[BioBERT NER Service\nHuggingFace Pipeline]
    D -->|Extracted entities\nSYMPTOM / CONDITION / BODY_PART| E[Neo4j Knowledge Graph\nDisease-Symptom Graph]

    E -->|Cypher: MATCH symptoms → diseases → urgency| F[Graph Probability Engine\nSUM weights per disease]
    F -->|Top diseases + max urgency| G[Rule-Based Triage Engine\nCRITICAL / HIGH / MEDIUM / LOW]

    G -->|Triage decision| H[(MongoDB\nSave Session)]
    H -->|Generate structured doc| I[Doctor Handoff Report]

    G -->|Triage result JSON| J[React UI: Result Display]
    J --> K[🚨 Urgency Badge\nColor-coded level]
    J --> L[📋 Recommended Action\nCall 911 / Go to ER / Urgent Care / GP]
    J --> M[🗺️ Google Maps\nNearest Hospitals]
    J --> N[📄 Download\nHandoff Report PDF]

    style A fill:#4A90D9,color:#fff
    style D fill:#7B68EE,color:#fff
    style E fill:#2ECC71,color:#fff
    style G fill:#E74C3C,color:#fff
    style H fill:#F39C12,color:#fff
    style I fill:#F39C12,color:#fff
```

## Urgency Level Color Codes

| Level | Color | Action |
|-------|-------|--------|
| 🔴 CRITICAL | Red | Call 911 immediately |
| 🟠 HIGH | Orange | Go to ER now |
| 🟡 MEDIUM | Yellow | Urgent care within 4 hours |
| 🟢 LOW | Green | Schedule GP appointment |

## Component Interaction Summary

```
User Input
    └─► BioBERT (NER) ──► Neo4j (Graph Query) ──► Triage Engine
                                                        │
                                              ┌─────────┴──────────┐
                                              ▼                    ▼
                                          MongoDB              React UI
                                       (Persistence)         (Display)
```
