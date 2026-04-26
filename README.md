# Aura — AI Mental Wellness Platform (Backend)

> FastAPI + LangGraph multi-agent backend powering mood analysis, AI coaching, journaling, wellness planning, and AI therapy.

**Live API:** [aurabd-production.up.railway.app](https://aurabd-production.up.railway.app) &nbsp;·&nbsp; **Frontend:** [Aura_fd](https://github.com/Bharath-tars/Aura_fd)

![Python](https://img.shields.io/badge/Python_3.12-3776AB?style=flat&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-FF6B35?style=flat)
![Gemini](https://img.shields.io/badge/Gemini_2.5_Flash-4285F4?style=flat&logo=google&logoColor=white)
![Railway](https://img.shields.io/badge/Deployed_on-Railway-0B0D0E?style=flat&logo=railway&logoColor=white)

---

## Features

- **AI Coach** — Streaming chat via SSE, multi-session, auto-named sessions, CBT/mindfulness persona
- **AI Therapist** — Separate LangGraph agent with semantic memory compaction, full platform context, calming DBT persona
- **Mood Tracker** — CRUD mood entries, analytics (trend, weekly averages, emotion frequency, factor impact)
- **Journal** — AI-powered sentiment analysis, theme extraction per entry
- **Wellness Plans** — AI-generated multi-step plans with task management and progress tracking
- **Cross-platform Analytics** — Aggregated stats across mood, journal, tasks, and wellness plans
- **Crisis Detection** — Dedicated node on every AI response path; escalates with resources at level ≥ 2

---

## Agent Architecture

```
User message
    │
    ▼
semantic_router  ──────────────────────────────────────────────────────────┐
    │                                                                       │
    ▼                                                                       │
context_loader                                                              │
    │                                                                       │
    ├──► wellness_coach                                                     │
    ├──► mood_analyzer                                                      │
    ├──► journal_insights                                                   │
    ├──► plan_generator                                                     │
    └──► crisis_direct  ◄──────────────────────────────────────────────────┘
    │
    ▼
crisis_detector (always runs)
    │
    ▼
response_synthesizer
    │
    ▼
SSE stream → client
```

**Therapist graph** (separate StateGraph):
`memory_loader → platform_loader → therapy_response → crisis_detector → memory_compactor`

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | FastAPI 0.115 + Python 3.12 |
| AI / Agents | LangGraph 0.2 + LangChain 0.3 + Google Gemini 2.5 Flash |
| Database | SQLite via SQLAlchemy 2.0 async + aiosqlite |
| Auth | JWT HS256, 30-day expiry, bcrypt (12 rounds) |
| Streaming | Server-Sent Events (SSE) |
| Containerisation | Docker |
| Hosting | Railway |

---

## Getting Started

```bash
python -m venv venv
source venv/Scripts/activate   # Windows
# source venv/bin/activate     # Mac/Linux

pip install -r requirements.txt

cp .env.example .env           # add GEMINI_API_KEY and SECRET_KEY

python init_db.py              # creates wellness.db

uvicorn main:app --reload --port 8000
# Swagger UI → http://localhost:8000/docs
```

**.env variables**
```
GEMINI_API_KEY=your_key_here
SECRET_KEY=any_32_char_random_string
DATABASE_URL=sqlite+aiosqlite:///./wellness.db
CORS_ORIGINS=http://localhost:5173
```

**Demo credentials**
```
Email:    demo@aura.app
Password: aura2025
```

---

## API Overview

| Resource | Endpoints |
|---|---|
| Auth | `POST /auth/register` · `POST /auth/login` · `PATCH /auth/profile` |
| Mood | `GET/POST /mood` · `PATCH/DELETE /mood/{id}` |
| Journal | `GET/POST /journal` · `GET/DELETE /journal/{id}` |
| Wellness | `GET/POST /wellness/plans` · `DELETE /wellness/plans/{id}` · task CRUD |
| Analytics | `GET /analytics/dashboard` |
| AI Coach | `GET/POST /chat/sessions` · `DELETE /chat/sessions/{id}` · `POST /chat/sessions/{id}/message` (SSE) |
| AI Therapist | `GET/POST /therapist/sessions` · `DELETE /therapist/sessions/{id}` · `POST /therapist/sessions/{id}/message` (SSE) |

Full interactive docs: [aurabd-production.up.railway.app/docs](https://aurabd-production.up.railway.app/docs)

---

## Project Structure

```
├── agents/
│   ├── graph.py               # Main wellness LangGraph StateGraph
│   ├── therapist_graph.py     # Therapist LangGraph StateGraph
│   ├── semantic_router.py     # Embedding-based intent routing (<50ms)
│   ├── state.py               # WellnessState TypedDict
│   ├── tools.py               # @tool DB accessors
│   └── nodes/                 # One file per agent node
├── graph_engine/
│   └── semantic_graph.py      # In-memory wellness knowledge graph
├── models/                    # SQLAlchemy ORM models
├── routers/                   # FastAPI routers (one per resource)
├── schemas/                   # Pydantic v2 request/response models
├── services/                  # Business logic layer
├── main.py                    # App entry point, router registration
└── init_db.py                 # DB init + semantic router centroid seeding
```

---

## Deployment

Hosted on **Railway** — every push to `main` triggers an automatic redeploy via Dockerfile.

---

## Developer

Built by [Sudarsanam Bharath](https://www.linkedin.com/in/bharath-sudarsanam/)
