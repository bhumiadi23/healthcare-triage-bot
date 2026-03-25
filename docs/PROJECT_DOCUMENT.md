# Healthcare Symptom Checker & Triage Bot
## Formal Project Document — Day 1

---

## 1. Problem Statement

### The ER Bottleneck Crisis

Emergency Rooms across the world face a critical structural inefficiency:

> **40–60% of all ER visits are non-emergencies** — patients with minor ailments like mild fever, headaches, or sprained ankles occupy beds, staff time, and diagnostic equipment. Meanwhile, patients experiencing heart attacks, strokes, or sepsis face **dangerous, life-threatening wait times** because the system is overwhelmed.

This is not a staffing problem — it is a **triage information problem**. Patients arrive without any pre-assessment. Nurses perform manual triage under pressure, and the system has no intelligent pre-filter.

### The Proposed Solution

A **conversational AI triage bot** that:
1. Collects patient symptoms in free-text natural language
2. Extracts medical entities using **BioBERT** (a biomedical NLP model)
3. Maps entities to a **Neo4j Knowledge Graph** of diseases, symptoms, and risk factors
4. Computes a **triage urgency score** using graph-traversal + rule-based logic
5. Presents a **React UI** with urgency level, recommended action, and nearest hospital (Google Maps)
6. Generates a structured **Doctor Handoff Report** stored in **MongoDB**

### Impact Goal
Reduce non-emergency ER visits by providing patients with accurate, instant pre-triage guidance — freeing ER capacity for critical cases.

---

## 2. Feature List

### MVP Features (In Scope)
| # | Feature | Priority |
|---|---------|----------|
| F1 | Free-text symptom input via chat interface | P0 |
| F2 | BioBERT-based Named Entity Recognition (NER) for symptom extraction | P0 |
| F3 | Neo4j Knowledge Graph with top 50 presenting symptoms | P0 |
| F4 | Rule-based Triage Engine (4 urgency levels) | P0 |
| F5 | Triage result display with urgency badge + recommended action | P0 |
| F6 | Doctor Handoff Report generation (PDF-ready) | P0 |
| F7 | MongoDB storage of patient session + report | P0 |
| F8 | Nearest hospital finder via Google Maps API | P1 |
| F9 | Patient history retrieval by session ID | P1 |

### Out of Scope (Post-MVP)
- Real-time doctor video consultation
- EHR/EMR system integration
- Prescription generation
- Multi-language support
- Mobile native app

### MVP Scope Boundary Statement
> *"For the MVP, we will populate the Neo4j Knowledge Graph with only the **top 50 most common presenting symptoms** to ensure the triage rules are 100% accurate and clinically validated before expansion."*

---

## 3. System Architecture

### 3.1 Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        REACT FRONTEND                           │
│   Chat UI  │  Triage Result Card  │  Hospital Map  │  Report    │
└──────────────────────────┬──────────────────────────────────────┘
                           │ REST API (JSON)
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FASTAPI BACKEND                            │
│   /chat  │  /triage  │  /report  │  /history  │  /hospitals     │
└────┬──────────────┬──────────────────────┬───────────────────────┘
     │              │                      │
     ▼              ▼                      ▼
┌─────────┐  ┌────────────┐        ┌─────────────┐
│ BioBERT │  │   Neo4j    │        │   MongoDB   │
│  (NER)  │  │  Knowledge │        │  (Patient   │
│ Service │  │   Graph    │        │   History + │
│         │  │ + Triage   │        │   Reports)  │
│ Extracts│  │  Engine    │        │             │
│ medical │  │            │        │             │
│entities │  │ Computes   │        │ Stores      │
│         │  │ urgency    │        │ sessions &  │
│         │  │ score      │        │ handoff doc │
└─────────┘  └────────────┘        └─────────────┘
```

### 3.2 Data Flow Flowchart

```
User Types Free-Text Symptoms
            │
            ▼
    ┌───────────────┐
    │  React UI     │  "I have chest pain, shortness of breath, and sweating"
    └──────┬────────┘
           │ POST /chat
           ▼
    ┌───────────────────────────────┐
    │  FastAPI: /chat endpoint      │
    └──────┬────────────────────────┘
           │
           ▼
    ┌───────────────────────────────┐
    │  BioBERT NER Service          │
    │  Input: raw text              │
    │  Output: [                    │
    │    {entity: "chest pain",     │
    │     label: "SYMPTOM"},        │
    │    {entity: "dyspnea",        │
    │     label: "SYMPTOM"},        │
    │    {entity: "diaphoresis",    │
    │     label: "SYMPTOM"}         │
    │  ]                            │
    └──────┬────────────────────────┘
           │ Extracted entities
           ▼
    ┌───────────────────────────────┐
    │  Neo4j Knowledge Graph        │
    │                               │
    │  MATCH (s:Symptom)-[:INDICATES│
    │  ]->(d:Disease)-[:HAS_URGENCY │
    │  ]->(u:UrgencyLevel)          │
    │                               │
    │  Returns: {                   │
    │    diseases: ["MI", "PE"],    │
    │    max_urgency: "CRITICAL",   │
    │    confidence: 0.94           │
    │  }                            │
    └──────┬────────────────────────┘
           │ Graph query result
           ▼
    ┌───────────────────────────────┐
    │  Rule-Based Triage Engine     │
    │                               │
    │  IF urgency == CRITICAL:      │
    │    → "Call 911 immediately"   │
    │  IF urgency == HIGH:          │
    │    → "Go to ER now"           │
    │  IF urgency == MEDIUM:        │
    │    → "Urgent care within 4h"  │
    │  IF urgency == LOW:           │
    │    → "Schedule appointment"   │
    └──────┬────────────────────────┘
           │ Triage decision
           ▼
    ┌───────────────────────────────┐
    │  MongoDB: Save Session        │
    │  Generate Doctor Handoff Doc  │
    └──────┬────────────────────────┘
           │ Response JSON
           ▼
    ┌───────────────────────────────┐
    │  React UI: Display Result     │
    │  • Urgency badge (color-coded)│
    │  • Recommended action         │
    │  • Possible conditions        │
    │  • Nearest hospitals (Maps)   │
    │  • Download Handoff Report    │
    └───────────────────────────────┘
```

### 3.3 Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Frontend | React 18 + TailwindCSS | Chat UI, triage display, maps |
| Backend | FastAPI (Python 3.11) | REST API, orchestration |
| NLP | BioBERT (HuggingFace) | Medical NER — symptom extraction |
| Knowledge Graph | Neo4j 5.x | Disease-symptom relationships, urgency scoring |
| Database | MongoDB Atlas | Patient sessions, handoff reports |
| Maps | Google Maps API | Nearest hospital finder |
| Containerization | Docker + Docker Compose | Local dev environment |

---

## 4. MongoDB Schema Design

### 4.1 Patient Session Collection (`patient_sessions`)

```json
{
  "_id": "ObjectId",
  "session_id": "uuid-v4",
  "created_at": "ISODate",
  "patient_info": {
    "age": "number",
    "sex": "string (M/F/Other)",
    "known_conditions": ["string"]
  },
  "conversation": [
    {
      "turn": 1,
      "user_input": "string (raw free-text)",
      "extracted_entities": [
        { "text": "string", "label": "SYMPTOM|CONDITION|BODY_PART", "confidence": 0.0 }
      ],
      "timestamp": "ISODate"
    }
  ],
  "triage_result": {
    "urgency_level": "CRITICAL|HIGH|MEDIUM|LOW",
    "urgency_score": "number (0-100)",
    "possible_conditions": ["string"],
    "recommended_action": "string",
    "confidence": "number (0-1)"
  },
  "status": "active|completed|abandoned"
}
```

### 4.2 Doctor Handoff Report Collection (`handoff_reports`)

```json
{
  "_id": "ObjectId",
  "report_id": "uuid-v4",
  "session_id": "uuid-v4 (ref: patient_sessions)",
  "generated_at": "ISODate",
  "patient_summary": {
    "age": "number",
    "sex": "string",
    "known_conditions": ["string"]
  },
  "chief_complaint": "string (auto-summarized from conversation)",
  "extracted_symptoms": [
    { "symptom": "string", "duration": "string", "severity": "mild|moderate|severe" }
  ],
  "differential_diagnosis": [
    { "condition": "string", "probability": "number", "icd10_code": "string" }
  ],
  "triage_decision": {
    "urgency_level": "string",
    "recommended_action": "string",
    "assigned_at": "ISODate"
  },
  "vital_flags": ["string"],
  "report_pdf_url": "string (S3 or local path)"
}
```

### 4.3 Indexes

```javascript
// Fast session lookup
db.patient_sessions.createIndex({ "session_id": 1 }, { unique: true })
db.patient_sessions.createIndex({ "created_at": -1 })

// Report lookup by session
db.handoff_reports.createIndex({ "session_id": 1 })
db.handoff_reports.createIndex({ "generated_at": -1 })
```

---

## 5. Neo4j Knowledge Graph Schema

### Node Types
```
(:Symptom { name, synonyms[], icd10_code })
(:Disease { name, icd10_code, description })
(:UrgencyLevel { level: "CRITICAL|HIGH|MEDIUM|LOW", score: 0-100 })
(:RiskFactor { name, type: "age|comorbidity|lifestyle" })
(:BodyPart { name, region })
```

### Relationship Types
```
(:Symptom)-[:INDICATES { weight: float }]->(:Disease)
(:Disease)-[:HAS_URGENCY]->(:UrgencyLevel)
(:Disease)-[:WORSENED_BY]->(:RiskFactor)
(:Symptom)-[:LOCATED_IN]->(:BodyPart)
(:Disease)-[:CO_OCCURS_WITH]->(:Disease)
```

### Triage Query (Cypher)
```cypher
MATCH (s:Symptom)-[r:INDICATES]->(d:Disease)-[:HAS_URGENCY]->(u:UrgencyLevel)
WHERE s.name IN $symptom_list
WITH d, u, SUM(r.weight) AS match_score
ORDER BY match_score DESC
RETURN d.name AS disease, u.level AS urgency, match_score
LIMIT 5
```

---

## 6. Team Roles & Ownership

| Role | Owner | Responsibilities |
|------|-------|-----------------|
| **NLP Engineer** | Team Member A | BioBERT model setup, HuggingFace pipeline, NER fine-tuning on medical corpus, entity normalization |
| **Knowledge Graph Engineer** | Team Member B | Neo4j schema design, populate top-50 symptom graph, Cypher triage queries, urgency scoring logic |
| **Backend Engineer** | Team Member C | FastAPI endpoints, orchestration between BioBERT + Neo4j + MongoDB, report generation |
| **Frontend Engineer** | Team Member D | React chat UI, triage result display, Google Maps integration, handoff report download |
| **Project Lead / DevOps** | Team Member E | Docker Compose setup, MongoDB schema, API contracts, documentation, KPI tracking |

### Ownership Matrix (RACI)
| Task | NLP Eng | KG Eng | Backend | Frontend | Lead |
|------|---------|--------|---------|----------|------|
| BioBERT NER pipeline | **R** | C | C | - | A |
| Neo4j graph population | C | **R** | C | - | A |
| Triage rule engine | C | **R** | C | - | A |
| FastAPI endpoints | C | C | **R** | C | A |
| React UI + Chat | - | - | C | **R** | A |
| Google Maps integration | - | - | C | **R** | A |
| MongoDB schema | C | C | **R** | - | A |
| Doctor Handoff Report | C | C | **R** | C | A |
| Docker / DevOps | - | - | C | - | **R** |

*R = Responsible, A = Accountable, C = Consulted*

---

## 7. Project Timeline (5-Day MVP)

| Day | Focus | Deliverable |
|-----|-------|-------------|
| Day 1 | Architecture & Planning | This document, folder scaffold, schema |
| Day 2 | NLP + Knowledge Graph | BioBERT NER working, Neo4j populated with 50 symptoms |
| Day 3 | Backend API | All FastAPI endpoints functional, triage engine live |
| Day 4 | Frontend | React chat UI, triage display, Maps integration |
| Day 5 | Integration & Demo | End-to-end flow, handoff report, final demo |

---

## 8. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| BioBERT inference too slow | Medium | High | Cache results, use smaller distilled model (Bio_ClinicalBERT) |
| Neo4j graph incomplete | Low | High | Strictly limit to 50 symptoms; validate each node |
| Google Maps API quota | Low | Medium | Mock hospital data as fallback |
| MongoDB schema changes mid-project | Medium | Medium | Version the schema from Day 1 |

---

*Document Version: 1.0 | Project: Healthcare Symptom Checker & Triage Bot | Day 1*
