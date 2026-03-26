<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/LangChain-RAG-1C3C3C?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white" />
  <img src="https://img.shields.io/badge/AWS_ECS-FF9900?style=for-the-badge&logo=amazonaws&logoColor=white" />
</p>

# Monster Resort Concierge

**A production-grade AI concierge system** that serves six fictional monster-themed resort properties. Guests chat with a gothic-persona agent that retrieves answers from a 7,000+ word knowledge base using hybrid RAG, books rooms via function-calling tools, generates PDF receipts, detects hallucinations in real time, and falls back across three LLM providers automatically -- all behind JWT auth, rate limiting, and Prometheus observability.

This isn't a wrapper around an API call. It's a fully wired backend: retrieval pipeline, agent loop, tool execution, hallucination scoring, conversation memory, database persistence, and CI/CD to AWS -- built to demonstrate how these systems work together in production.

---

## What the Agent Actually Does

```
Guest: "I'd like to book a coffin suite at Vampire Manor for two nights"
```

1. Message is validated, sanitized, and authenticated (JWT or API key)
2. RAG pipeline runs hybrid search -- BM25 keyword + dense vector retrieval -- fused via Reciprocal Rank Fusion, then reranked by a cross-encoder
3. Top 5 context chunks are injected into the system prompt with source attribution tags
4. LLM (OpenAI/Anthropic/Ollama) generates a response and decides to call `book_room`
5. Tool executes: validates hotel against a 6-property registry, checks dates, writes to SQLite, generates a PDF receipt
6. Tool results feed back to the LLM for a synthesis response
7. Hallucination detector scores the final output (context overlap + semantic similarity + source attribution) and assigns HIGH/MEDIUM/LOW confidence
8. Response streams back to the Gradio chat UI with confidence metadata
9. Prometheus captures request latency, token usage, RAG retrieval time, and confidence distribution

---

## Architecture

```
                          +-----------------+
                          |   Gradio Chat   |  :7861
                          |   (Gothic UI)   |
                          +--------+--------+
                                   |
                          +--------v--------+
                          |    FastAPI       |  :8000
                          |  /chat  /metrics |
                          +--------+--------+
                                   |
              +--------------------+--------------------+
              |                    |                     |
     +--------v--------+  +-------v--------+  +--------v--------+
     |   Auth & Rate   |  |   LLM Router   |  |   RAG Pipeline  |
     |   Limiting      |  |                |  |                 |
     | - JWT tokens    |  | - OpenAI       |  | - BM25 keyword  |
     | - API keys      |  | - Anthropic    |  | - Dense vector  |
     |   (SHA-256)     |  | - Ollama       |  |   (ChromaDB)    |
     | - SlowAPI       |  | - Auto-fallback|  | - RRF fusion    |
     | - Input         |  |                |  | - Cross-encoder |
     |   sanitization  |  +-------+--------+  |   reranking     |
     +-----------------+          |            +--------+--------+
                                  |                     |
              +-------------------v---------------------+
              |              Agent Loop                  |
              |  LLM call -> tool decision -> execute -> |
              |  results -> synthesis call -> respond     |
              +-------------------+---------------------+
                                  |
         +------------------------+------------------------+
         |                        |                        |
+--------v--------+  +-----------v---------+  +-----------v----------+
|     Tools       |  |   Hallucination     |  |    Observability     |
|                 |  |   Detector          |  |                      |
| - book_room     |  | - Context overlap   |  | - Prometheus metrics |
| - get_booking   |  | - Semantic sim.     |  |   (8 metric types)  |
| - search_       |  | - Source            |  | - MLflow experiment  |
|   amenities     |  |   attribution       |  |   tracking           |
| - PDF receipts  |  | - 3-factor scoring  |  | - Structured logging |
+--------+--------+  +---------------------+  +----------------------+
         |
+--------v--------+
|    SQLite DB     |
| - bookings      |
| - sessions      |
| - messages       |
| - API key audit  |
+-----------------+
```

---

## The RAG Pipeline (in detail)

This is the core of the system. Not a single-call embedding lookup -- a three-stage retrieval pipeline:

**Stage 1 -- Hybrid Retrieval**
| Method | What it does | Why both |
|---|---|---|
| BM25 (keyword) | Exact term matching via `BM25Okapi` over tokenized documents | Catches proper nouns, specific room names, exact phrases |
| Dense vectors | Semantic search via `all-MiniLM-L6-v2` embeddings in ChromaDB | Catches meaning-based queries where exact words differ |

**Stage 2 -- Reciprocal Rank Fusion (RRF)**

Merges both result sets with weighted scoring: `score = sum(1 / (60 + rank))` across lists. BM25 weighted at 0.4, dense at 0.6. This prevents either method from dominating and produces a balanced candidate set.

**Stage 3 -- Cross-Encoder Reranking**

Final candidates are rescored by `BAAI/bge-reranker-base`, which reads each (query, document) pair jointly -- far more accurate than embedding similarity alone. Top 5 results are returned with 300-second caching.

**Knowledge Base:** 7,000+ words across 5 files covering 6 properties, 20+ room types, 50+ amenities, 40+ activities, seasonal events, and 50+ FAQ pairs. Plus a 150+ entry QA dataset for evaluation.

---

## Hallucination Detection

Every response is scored before being returned. Three factors, weighted:

| Factor | Weight | Method |
|---|---|---|
| Context Overlap | 30% | Token-level intersection between response and retrieved context |
| Semantic Similarity | 50% | Cosine similarity of sentence embeddings (response vs. context) |
| Source Attribution | 20% | Per-sentence grounding check -- does each claim trace back to a source? |

**Result:** A 0-1.0 confidence score mapped to HIGH (>0.7), MEDIUM (>0.4), or LOW (<0.4). Returned in every API response and tracked as a Prometheus histogram.

---

## Multi-Provider LLM Routing

The `ModelRouter` abstracts away provider differences behind a unified interface:

| Provider | Default Model | Format |
|---|---|---|
| OpenAI | `gpt-4o-mini` | Native OpenAI API |
| Anthropic | `claude-sonnet-4-20250514` | Translated from OpenAI message format |
| Ollama | `llama3` (local) | OpenAI-compatible HTTP |

**Fallback logic:** Providers are tried in configurable priority order. If the primary fails (network error, rate limit, auth failure), the router catches the exception and tries the next provider. If all fail, the last error is raised. Swap providers via a single env var -- no code changes.

---

## Tool-Calling Agent

The agent operates in a two-phase loop:

**Phase 1:** LLM receives the user message + RAG context + conversation history + tool schemas. It either responds directly or returns tool calls.

**Phase 2:** If tools were called, results are appended to the conversation and the LLM is called again to synthesize a final response incorporating the tool output.

| Tool | What it does |
|---|---|
| `book_room` | Validates hotel against 6-property registry, validates dates, writes booking to SQLite, generates PDF receipt |
| `get_booking` | Retrieves booking details by reference ID |
| `search_amenities` | Runs a RAG query against the knowledge base and returns relevant context |

---

## Security

| Layer | Implementation |
|---|---|
| Authentication | Dual-mode: JWT tokens + API keys (prefixed `mr_`, stored as SHA-256 hashes) |
| Key management | Rotation (90-day default), revocation, per-endpoint usage audit logging |
| Rate limiting | Per-IP throttling via SlowAPI, configurable per-minute limit |
| Input validation | Pydantic models + bleach sanitization on all user input |
| Tool validation | Hotel names validated against hardcoded registry -- LLM cannot hallucinate a property name into a tool call |
| Container | Non-root user, health checks, no secrets in image |

---

## Observability

**Prometheus Metrics** (exposed at `/metrics`):

| Metric | Type | Tracks |
|---|---|---|
| `mrc_http_requests_total` | Counter | Request volume by method, path, status |
| `mrc_http_request_latency_seconds` | Histogram | Response time distribution per endpoint |
| `mrc_errors_total` | Counter | Exceptions by error type |
| `mrc_bookings_total` | Counter | Booking volume by hotel property |
| `mrc_ai_tokens_total` | Counter | Token consumption per LLM model |
| `mrc_active_sessions` | Gauge | Live conversation sessions |
| `mrc_response_confidence` | Histogram | Hallucination score distribution |
| `mrc_hallucinations_detected` | Counter | Count by confidence level |

**Full stack:** Prometheus + Grafana dashboards + MLflow experiment tracking -- all wired in `docker-compose.yml`.

---

## Conversation Memory

Sessions persist across turns with auto-summarization:

- Messages stored in SQLite, keyed by `session_id`
- After 12 messages, the system auto-summarizes the conversation via LLM (with regex fallback) and prunes older messages
- Summaries are prepended to future context, keeping the agent aware of conversation history without unbounded token growth

---

## Tech Stack

| Layer | Technology |
|---|---|
| **API** | FastAPI, Pydantic, Uvicorn |
| **LLM** | OpenAI, Anthropic, Ollama |
| **RAG** | LangChain, ChromaDB, HuggingFace Embeddings, BM25, BAAI cross-encoder |
| **Evaluation** | RAGAS (faithfulness, relevance, recall) |
| **Database** | SQLite, SQLAlchemy, Alembic migrations |
| **Auth** | JWT (PyJWT), bcrypt, SHA-256 API key hashing |
| **Monitoring** | Prometheus, Grafana, MLflow |
| **UI** | Gradio (custom gothic theme) |
| **Deployment** | Docker, docker-compose (4-service stack), AWS ECS/ECR |
| **CI/CD** | GitHub Actions (lint, test, build, deploy) |
| **Testing** | pytest (15 test files), pytest-cov, pytest-asyncio |

---

## Project Structure

```
app/
  main.py                # FastAPI app, /chat endpoint, two-phase agent loop
  config.py              # Pydantic settings -- all config from env vars
  llm_providers.py       # ModelRouter + OpenAI/Anthropic/Ollama providers
  advanced_rag.py        # Hybrid RAG: BM25 + dense + RRF + cross-encoder reranking
  langchain_rag.py       # LangChain RAG integration
  hallucination.py       # 3-factor hallucination scoring
  tools.py               # Tool registry: book_room, get_booking, search_amenities
  database.py            # SQLite schema, migrations, booking/session persistence
  memory.py              # Conversation memory with auto-summarization
  auth.py                # JWT creation and verification
  security.py            # API key manager (hash, rotate, audit) + rate limiting
  monitoring.py          # Prometheus metric definitions + HTTP middleware
  mlflow_tracking.py     # MLflow experiment tracking integration
  pdf_generator.py       # ReportLab PDF receipt generation
  validation.py          # Input sanitization and Pydantic validation

data/
  knowledge/             # 5 knowledge base files (7,000+ words)
  concierge_qa.json      # 150+ QA pairs for evaluation and fine-tuning

scripts/
  benchmark_rag.py       # RAG retrieval performance benchmarking
  finetune_lora.py       # LoRA fine-tuning script
  generate_synthetic_dataset.py
  run_rag_experiment.py

tests/                   # 15 test files covering API, RAG, auth, booking, providers
notebooks/               # RAGAS evaluation, LoRA comparison, experimentation
deploy/aws/              # ECS task definition, ECR push, deploy scripts
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- At least one LLM provider: OpenAI API key, Anthropic API key, or [Ollama](https://ollama.ai) running locally

### Local Setup

```bash
# Clone
git clone https://github.com/AkinCodes/monster-resort-concierge.git
cd monster-resort-concierge

# Environment
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt

# Configure -- set at least one LLM provider key
cp .env.example .env
# MRC_OPENAI_API_KEY=sk-...
# MRC_ANTHROPIC_API_KEY=sk-ant-...
# MRC_API_KEY=your-api-key-here

# Ingest knowledge base into ChromaDB
python inspect_and_ingest_rag.py

# Start the server
uvicorn app.main:app --reload
```

API: `http://localhost:8000` | Chat UI: `http://localhost:7861` (run `python chat_ui.py`)

### Docker (full stack)

```bash
docker compose up --build
```

Starts 4 services: API (:8000), Prometheus (:9090), Grafana (:3000), MLflow (:5000)

### Tests

```bash
pytest --cov=app --cov-report=term-missing
```

---

## API

**POST** `/chat`

```json
{
  "session_id": "optional-uuid",
  "message": "What spa treatments does the Mummy Resort offer?"
}
```

**Response:**

```json
{
  "ok": true,
  "reply": "At The Mummy Resort & Tomb-Service, indulge in our Eternal Preservation Spa...",
  "session_id": "generated-or-provided-uuid",
  "tools_used": [],
  "confidence": {
    "overall_score": 0.87,
    "level": "HIGH",
    "context_overlap_score": 0.82,
    "semantic_similarity_score": 0.91,
    "source_attribution_score": 0.85
  },
  "provider": "openai"
}
```

**GET** `/metrics` -- Prometheus text format

---

## The Six Properties

| Property | Theme | Location |
|---|---|---|
| The Mummy Resort & Tomb-Service | Ancient Egyptian luxury | Sahara Desert |
| The Werewolf Lodge: Moon & Moor | Wilderness retreat | Scottish Highlands |
| Castle Frankenstein: High Voltage Luxury | Mad science elegance | Bavarian Alps |
| Vampire Manor: Eternal Night Inn | Gothic nocturnal palace | Transylvania |
| Zombie Bed & Breakfast: Bites & Beds | New Orleans undead charm | French Quarter |
| Ghostly B&B: Spectral Stay | Ethereal Victorian mansion | Multiple dimensions |

---

## CI/CD Pipeline

GitHub Actions on every push to `main`:

1. **Lint** -- flake8 across `app/` and `tests/`
2. **Test** -- full pytest suite with coverage report
3. **Deploy** -- Docker build, push to AWS ECR, rolling deploy to ECS

---

## License

This project is for portfolio and educational purposes.
