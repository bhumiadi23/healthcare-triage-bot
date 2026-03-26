<div align="center">
  
  <h1>🏥 Healthcare Triage Bot</h1>
  
  <p><strong>An AI-powered pre-triage system designed to reduce ER overcrowding by intelligently routing patients to the precise level of care they need using NLP & Knowledge Graphs.</strong></p>

  [![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
  [![Python](https://img.shields.io/badge/Python-3.11-3776AB.svg?logo=python&logoColor=white)](https://python.org)
  [![React](https://img.shields.io/badge/React-18.2-61DAFB.svg?logo=react&logoColor=black)](https://reactjs.org)
  [![FastAPI](https://img.shields.io/badge/FastAPI-0.104-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
  [![Neo4j](https://img.shields.io/badge/Neo4j-AuraDB-018bff.svg?logo=neo4j&logoColor=white)](https://neo4j.com)

  *Built with extreme focus on UI/UX, accurate NLP entity extraction, and lightning-fast graph traversal.*

</div>

---

## ⚡ The Problem & Solution
**40–60% of ER visits are non-emergencies.** This bot acts as an intelligent digital frontline. It pre-triages patients instantly using **BioBERT** for symptom extraction and a customized **Neo4j Medical Knowledge Graph** to ensure critical patients are flagged unconditionally while non-critical patients are diverted to urgent clinics or GPs.

## ⭐ Key Features

- **🎙️ Real-time Voice Dictation**  
  Hands-free symptom reporting using the native Web Speech API—speak your symptoms directly into the chat!
- **✨ Premium Glassmorphic UI**  
  A breathtaking, highly-animated interface built purely with CSS. Includes staggered reveals, fluid spring-animations, tracking orbs, and pulsing mic indicators.
- **🧠 BioBERT + Lexical Fallback NER**  
  Highly accurate Named Entity Recognition that extracts both clinical terminology (via Transformers) and conversational colloquialisms like *"tummy ache"* or *"fever"*.
- **🕸️ Neo4j Knowledge Graph**  
  Over 100+ interconnected diseases, symptoms, urgencies, and risk factors resolving top diagnoses via weighted graph queries.
- **⚡ Async FastAPI Backend**  
  High-performance Python backend connecting the HuggingFace NLP models to the Graph Database and standard NoSQL history stores.

---

## 🏗️ Architecture

```mermaid
graph TD;
    A[React.js Frontend\n(Voice + Chat)] -->|Symptom Text| B(FastAPI Backend);
    B --> C{NER Engine};
    C -->|Clinical NER| D[BioBERT Model];
    C -->|Synonym Matching| E[Lexical Map];
    D --> F[Extracted Entities];
    E --> F;
    F -->|Nodes matched| G[(Neo4j Knowledge Graph)];
    G -->|Triage Rules & Differentials| B;
    B --> A;
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | React 18, Native CSS Keyframes, Web Speech API |
| **Backend** | FastAPI (Python 3.11), Uvicorn, Pydantic |
| **NLP** | HuggingFace Transformers (`d4data/biomedical-ner-all`) |
| **Knowledge Graph** | Neo4j AuraDB (Cloud) / Neo4j 5 (Local) |
| **Database** | MongoDB 7 (Patient history & logs) |

---

## 🚀 Quick Start (Docker)

The fastest way to run the entire stack is with Docker (spins up the Frontend, Backend, MongoDB, and Neo4j automatically).

```bash
# 1. Clone the repository
git clone https://github.com/bhumiadi23/healthcare-triage-bot.git
cd healthcare-triage-bot

# 2. Set up environment variables
cp .env.example .env          

# 3. Build and launch
docker-compose up --build
```
> **Ports Unlocked:**
> - Frontend UI: [http://localhost:3000](http://localhost:3000)
> - Backend API Docs: [http://localhost:8000/docs](http://localhost:8000/docs)
> - Neo4j Browser: [http://localhost:7474](http://localhost:7474)

---

## 🌱 Seeding the Knowledge Graph

*Before your first run*, you must populate the Neo4j Graph with diseases and symptoms.

```bash
cd knowledge-graph
pip install neo4j python-dotenv
python seed_graph.py
```
*This injects over 100+ conditions including Myocardial Infarctions, Sepsis, COVID-19, and minor ailments ranging across CRITICAL, HIGH, MEDIUM, and LOW urgencies.*

---

## 📊 Triage Levels Explained

| Level | Urgency Score | Recommended Action |
|-------|--------------|--------------------|
| 🔴 **CRITICAL** | `90 - 100` | Call 911 immediately or go to the nearest ER. |
| 🟠 **HIGH** | `70 - 89` | Go to the ER or seek medical care within 1-2 hours. |
| 🟡 **MEDIUM** | `40 - 69` | Visit Urgent Care within 4-12 hours. |
| 🟢 **LOW** | `10 - 39` | Schedule an outpatient GP appointment at convenience. |

---

<div align="center">
  <p><i>Give this repository a ⭐️ if it helped you!</i></p>
</div>
