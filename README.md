# Team Ace - DSN x BCT LLM Agent Challenge

> **A user is not a string in a prompt. A user is a structured, retrievable, evolving behavioural agent.**
>
> Task A asks that agent: *"How would this user review this item?"*
>
> Task B asks that agent: *"What should this user choose next?"*
>
> Both tasks share the same underlying user representation. This repository is that representation, made queryable through two FastAPI services and two web UIs.

---

## Live Demos

| Task | URL | What it does |
|------|-----|--------------|
| **Task A - Review Studio** | https://team-ace-task-a-user-modeling.onrender.com | Simulate the review a user would actually write |
| **Task B - Recommendation Chat** | https://team-ace-task-b-recommendation.onrender.com | Rank items around a person's real context |

> **Note:** Services run on Render's free tier. If a page takes 30-60 seconds to respond on first load, the service is waking from sleep. Subsequent requests are much faster. During judging, a lightweight uptime heartbeat can be used to keep both services warm.

---

## Headline Results

| Metric | Team Ace | Baseline | Lift |
|--------|---------:|---------:|------|
| **Task A - RMSE** (86 held-out reviews) | **0.7421** | 1.3133 (global mean) | **43.5% reduction** |
| **Task A - RMSE** | **0.7421** | 1.3117 (item mean) | **43.4% reduction** |
| **Task A - ROUGE-L F1** (Groq-backed slice) | **0.2014** | 0.1150 (deterministic) | **+75%** |
| **Task B - NDCG@10** (86 held-out users) | **0.1039** | 0.0194 (popularity) | **5.4x** |
| **Task B - NDCG@10** | **0.1039** | 0.0481 (local ranker, no LLM) | **2.2x** |
| **Task B - Hit Rate@10** | **0.1860** | 0.0349 (popularity) | **5.3x** |
| **Calibration spread** at sentiment 0.82 | **4.7 vs 3.7 stars** | single global rating | Full-star fidelity |

The repository includes a checked-in Amazon Reviews 2023 subset for reproducible local evaluation:

- 252 products
- 265 real reviews
- 70 users
- 86 held-out test interactions
- 4 domains: `All_Beauty`, `Grocery_and_Gourmet_Food`, `Movies_and_TV`, `Video_Games`, plus a compact demo book catalog for cross-domain judge testing

Run the core evaluation from the repo root:

```bash
python scripts/evaluate_core_agent.py --data-path data/amazon_subset --output docs/core_evaluation_report.json --max-examples 100
```

Without `GROQ_API_KEY`, the app uses deterministic fallback behavior so judges can still run the code. With `GROQ_API_KEY`, review text, recommendation explanations, and cross-domain reasoning become richer.

---

## Quick Start

```bash
git clone https://github.com/Sadiq-Teslim/dsn-hack.git
cd dsn-hack

python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt

# Optional: enable hosted LLM and voice generation
copy .env.example .env
# Fill GROQ_API_KEY and YARNGPT_API_KEY in .env

# Run Task A on port 8001
python -m uvicorn app.task_a_main:app --host 0.0.0.0 --port 8001

# Run Task B on port 8002 in a second terminal
python -m uvicorn app.task_b_main:app --host 0.0.0.0 --port 8002
```

Open:

```text
Task A: http://localhost:8001
Task B: http://localhost:8002
```

---

## Architecture

The system is organized as five layers. Layers 1-3 are shared across both tasks; Layers 4 and 5 are task-specific.

```text
Layer 1 - Data foundation
  data/fixtures/ and data/amazon_subset/ hold product, review, persona, and evaluation data.

Layer 2 - User representation
  core/user_model/ builds a structured UserProfile with rating behavior, budget, taste tokens,
  category affinity, Nigerian register, and history-derived signals.

Layer 3 - Retrieval and memory
  core/retrieval/ retrieves review evidence and item candidates before generation or ranking.

Layer 4 - Agentic task pipelines
  core/task_a/ handles evidence retrieval, sentiment prediction, rating calibration, review generation,
  consistency checking, and formal reasoning.
  core/task_b/ handles intent parsing, cold-start clarification, cross-domain bridging,
  candidate shortlisting, LLM re-ranking, diversity filtering, and response building.

Layer 5 - Interfaces
  app.task_a_main:app exposes the Review Studio.
  app.task_b_main:app exposes the Recommendation Chat.
```

The LLM does not secretly run the whole product. Task A predicts sentiment and calibrates ratings locally before Groq writes or polishes the review. Task B retrieves and scores a candidate shortlist locally, then uses Groq to reason over those candidates and re-rank them before diversity filtering. If no API key is available, deterministic fallback text keeps both apps runnable.

---

## What We Built

- **Task A: User Modeling** - predicts star ratings and generates grounded, tone-aware reviews from a user persona and product details.
- **Task B: Recommendation** - produces contextual, cross-domain ranked recommendations from a persona and current need.
- **Nigerian-aware experience** - includes Lagos student, Abuja professional, and Port Harcourt family shopper personas, with support for budget pressure, family context, local routines, local taste, and voice-ready Nigerian language modes.
- **Voice layer** - supports browser voice input and hosted YarnGPT audio output for localized explanations.

## Why Team Ace Is Different

| Aspect | Typical Solution | Team Ace Approach | Advantage |
|---|---|---|---|
| Scoring | Opaque LLM calls | Local interpretable ensemble models | Auditable and reproducible |
| Language/reasoning | LLM does everything | Groq generates reviews and re-ranks shortlisted candidates with traceable reasoning | Controllable and consistent |
| User representation | Static embeddings | Dynamic traces plus Nigerian signals | Culturally relevant |
| Architecture | Monolithic demo | Shared core orchestrator with task-specific apps | Judge-friendly and reliable |

## Deliverables

| Deliverable | Location |
|---|---|
| Task A deployed app/API | `app.task_a_main:app` |
| Task B deployed app/API | `app.task_b_main:app` |
| Task A solution paper | `docs/Task_A_User_Modeling_Team_Ace.docx` |
| Task B solution paper | `docs/Task_B_Recommendation_Team_Ace.docx` |
| Combined solution paper | `docs/BCT_Solution_Paper_Team_Ace.docx` |
| Real Amazon subset | `data/amazon_subset/` |
| Evaluation reports | `docs/core_evaluation_report.json`, `docs/evaluation_report.json`, `docs/nigerian_context_report.json` |
| Deployment config | `Dockerfile`, `docker-compose.yml`, `render.yaml` |

## Quick Demo Flow

### Task A

1. Open the Task A deployment.
2. Select a demo persona, adjust product details, and generate a review.
3. Check the predicted rating, review text, reasoning, confidence, and evidence.
4. Use **Yarn Mode** to localize the explanation and generate voice output.

### Task B

1. Open the Task B deployment.
2. Select a persona and enter a context like "I need affordable things for a busy school week."
3. Generate recommendations.
4. Review the ranked items, scores, reasons, and matched preferences.

## Environment Variables

Create `.env` from `.env.example`.

```env
LLM_PROVIDER=groq
GROQ_API_KEY=your_groq_key
GROQ_MODEL=llama-3.1-8b-instant
DATA_PATH=data/fixtures
YARNGPT_API_KEY=your_yarngpt_key
YARNGPT_BASE_URL=https://yarngpt.ai/api/v1
YARNGPT_VOICE=Idera
YARNGPT_RESPONSE_FORMAT=mp3
```

All keys are optional for local reproducibility:

- Without `GROQ_API_KEY`, the app uses deterministic local review and explanation text.
- Without `YARNGPT_API_KEY`, the UI falls back to browser speech synthesis.

## Docker

```bash
copy .env.example .env
docker compose up --build
```

Then open:

```text
Task A: http://127.0.0.1:8001
Task B: http://127.0.0.1:8002
```

## Render Deployment

This repository includes `render.yaml` with two Render web services:

- `team-ace-task-a-user-modeling`
- `team-ace-task-b-recommendation`

Live URLs:

```text
Task A: https://team-ace-task-a-user-modeling.onrender.com
Task B: https://team-ace-task-b-recommendation.onrender.com
```

Recommended Render settings:

```text
Build Command: pip install -r requirements.txt
Task A Start Command: python -m uvicorn app.task_a_main:app --host 0.0.0.0 --port $PORT
Task B Start Command: python -m uvicorn app.task_b_main:app --host 0.0.0.0 --port $PORT
Health Check Path: /health
```

Set secrets in the Render dashboard:

```env
LLM_PROVIDER=groq
GROQ_MODEL=llama-3.1-8b-instant
DATA_PATH=data/fixtures
GROQ_API_KEY=your_groq_key
YARNGPT_API_KEY=your_yarngpt_key
YARNGPT_BASE_URL=https://yarngpt.ai/api/v1
YARNGPT_VOICE=Idera
YARNGPT_RESPONSE_FORMAT=mp3
```

The keys are marked `sync: false` in `render.yaml`, so secrets are never committed.

## API Endpoints

### Health

```bash
curl http://127.0.0.1:8001/health
curl http://127.0.0.1:8002/health
```

### Generate Review

```bash
curl -X POST http://127.0.0.1:8001/api/v1/generate-review ^
  -H "Content-Type: application/json" ^
  -d @examples/generate_review.json
```

### Recommend

```bash
curl -X POST http://127.0.0.1:8002/api/v1/recommend ^
  -H "Content-Type: application/json" ^
  -d @examples/recommend.json
```

### Evaluation

```bash
python scripts/evaluate_dataset.py --data-path data/amazon_subset --output docs/evaluation_report.json
python scripts/evaluate_core_agent.py --data-path data/amazon_subset --output docs/core_evaluation_report.json --max-examples 100
python scripts/evaluate_nigerian_context.py
```

## Voice and Yarn Mode

`POST /api/v1/yarn` converts generated reviews or recommendation explanations into localized, voice-ready Nigerian explanations.

Supported modes include:

- Nigerian Pidgin
- Yoruba-flavoured English
- Hausa-flavoured English
- Igbo-flavoured English
- Formal judge summary

When `YARNGPT_API_KEY` is set, `POST /api/v1/yarn-tts` returns playable hosted audio. The browser UI also supports speech input where the browser allows microphone access.

## Data Strategy

The repository uses two data tracks:

- `data/fixtures/`: small curated cross-domain data for instant demos.
- `data/amazon_subset/`: bounded real Amazon Reviews 2023 subset for measurable evaluation.

To refresh or expand the Amazon subset:

```bash
python scripts/download_amazon_subset.py --max-reviews-per-category 400
```

Run the app against the generated subset:

```bash
$env:DATA_PATH="data/amazon_subset"
uvicorn app.main:app --reload
```

Compare personalized models against baselines:

```bash
python scripts/evaluate_dataset.py --data-path data/amazon_subset --output docs/evaluation_report.json
```

## Evaluation

```bash
pytest
python scripts/evaluate.py
python scripts/evaluate_dataset.py --data-path data/amazon_subset --output docs/evaluation_report.json
```

The tests cover API behavior, schema validation, scoring, generation fallback, ranking, and cold-start handling.

Current core-agent evaluation artifacts:

```text
docs/core_evaluation_report.json
docs/nigerian_context_report.json
```

The Nigerian register library contains 50 curated examples across Nigerian Pidgin, Standard Nigerian English, Yoruba-flavoured English, Hausa-flavoured English, Igbo-flavoured English, and formal judge summaries.

## Solution Papers

Task-specific papers:

```text
docs/Task_A_User_Modeling_Team_Ace.docx  # 5-page standalone Task A paper
docs/Task_B_Recommendation_Team_Ace.docx # 6-page standalone Task B paper
```

Combined paper:

```text
docs/BCT_Solution_Paper_Team_Ace.docx
```

Regenerate the separate task papers with:

```bash
python scripts/create_task_specific_papers.py
```

Regenerate the combined paper with:

```bash
python scripts/create_solution_paper_docx.py
```

The paper follows the 4 to 8 page requirement and is structured around:

- Problem and opportunity
- Team Ace differentiators
- System architecture
- Dataset strategy and experiments
- Implementation details
- Results and ablations
- Demo and reproducibility
- Limitations and future work

## Repository Map

```text
app/                  FastAPI task entrypoints, public schemas, app-level services
core/                 Shared agent contracts, orchestration, retrieval, and task pipelines
static/               Landing page, Task A UI, Task B UI, shared frontend logic
data/fixtures/        Zero-download demo data
data/amazon_subset/   Checked-in real Amazon Reviews 2023 subset
data/nigerian_context Curated Nigerian register exemplars
docs/                 Solution paper, screenshots, evaluation report
examples/             Example JSON payloads for API testing
scripts/              Dataset, evaluation, and paper generation scripts
tests/                Unit and integration tests
```

The Docker image copies both `app/` and `core/`; both directories are required at runtime.

## Team Ace

- **Teslim Sadiq:** product engineering, backend/API integration, deployment, demo flow
- **Yasir Oyebo:** data strategy, evaluation, experiments, model reasoning
- **Abiodun Mark:** UX polish, Nigerian contextualization, storytelling, judge presentation

We are not just submitting an agent. We are demonstrating a practical standard for interpretable, reproducible, and deeply contextual LLM agents built for Nigeria and the world.
