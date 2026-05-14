# Team Ace: Dynamic User Modeling and Contextual Recommendation

**DSN x BCT LLM Agent Challenge, Data & AI Summit Hackathon 3.0**

Team Ace built one unified agent studio for both challenge tasks: simulating how a user would review an unseen item and recommending what they are likely to choose next.

The core idea is simple: users are not static profiles. They are changing stories shaped by ratings, reviews, budgets, routines, family needs, location, language, and culture. Our system turns those signals into dynamic behavioral personas that can power both review simulation and personalized recommendation.

## What We Built

- **Task A: User Modeling**
  Predicts star ratings and generates grounded, tone-aware reviews from a user persona and product details.

- **Task B: Recommendation**
  Produces contextual, cross-domain ranked recommendations from a persona and current need.

- **Nigerian-aware experience**
  Includes Lagos student, Abuja professional, and Port Harcourt family shopper personas, with support for budget pressure, family context, local routines, harmattan/weather cues, local taste, and voice-ready Nigerian language modes.

- **Voice layer**
  Supports browser voice input and hosted YarnGPT audio output for localized explanations.

## Why Team Ace Is Different

| Aspect | Typical Solution | Team Ace Approach | Advantage |
|---|---|---|---|
| Scoring | Opaque LLM calls | Local interpretable ensemble models | Auditable and reproducible |
| Language generation | LLM does everything | Groq only after local decisions | Controllable and consistent |
| User representation | Static embeddings | Dynamic traces plus Nigerian signals | Culturally relevant |
| Architecture | Monolithic demo | Bounded agentic workflow | Judge-friendly and reliable |

The LLM does not secretly decide the score. Local models first predict ratings and rank items. Groq then turns the validated decision into fluent reviews and explanations. If no API key is available, deterministic fallback text keeps the app runnable.

## Key Results

Current checked-in real Amazon Reviews 2023 subset:

- 252 products
- 265 real reviews
- 70 users
- 86 held-out test interactions
- 4 domains: `All_Beauty`, `Grocery_and_Gourmet_Food`, `Movies_and_TV`, `Video_Games`

| Metric | Team Ace | Baseline |
|---|---:|---:|
| Task A RMSE | `0.7357` | `1.3133` |
| Task B NDCG@10 | `0.0481` | `0.0194` |
| Task B Hit Rate@10 | `0.1163` | `0.0349` |

The ranking scores are intentionally reported on a small, checked-in subset so judges can inspect and reproduce the evidence. The important signal is the ablation direction: personalization beats global rating and popularity baselines.

## Deliverables

| Deliverable | Location |
|---|---|
| Web app and API | FastAPI service in `app/`, UI in `static/` |
| Solution paper | `docs/BCT_Solution_Paper_Team_Ace.docx` |
| Real Amazon subset | `data/amazon_subset/` |
| Evaluation report | `docs/evaluation_report.json` |
| Deployment config | `Dockerfile`, `docker-compose.yml`, `render.yaml` |

## Quick Demo Flow

1. Open the app.
2. Go to **Task A**.
3. Select a demo persona, adjust product details, and generate a review.
4. Check the predicted rating, review text, reasoning, confidence, and evidence.
5. Use **Yarn Mode** to localize the explanation and generate voice output.
6. Go to **Task B**.
7. Select a persona, enter a context like "I need affordable things for a busy school week", and generate recommendations.
8. Review the ranked items, scores, reasons, and matched preferences.

## Quick Start

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000
```

## Environment Variables

Create `.env` from `.env.example`.

```env
GROQ_API_KEY=your_groq_key
GROQ_MODEL=llama-3.1-8b-instant
YARNGPT_API_KEY=your_yarngpt_key
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
http://127.0.0.1:8000
```

## Render Deployment

This repository includes `render.yaml` for Render deployment.

Recommended Render settings:

```text
Build Command: pip install -r requirements.txt
Start Command: python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT
Health Check Path: /health
```

Set secrets in the Render dashboard:

```env
GROQ_API_KEY=your_groq_key
YARNGPT_API_KEY=your_yarngpt_key
```

The keys are marked `sync: false` in `render.yaml`, so secrets are never committed.

## API Endpoints

### Health

```bash
curl http://127.0.0.1:8000/health
```

### Generate Review

```bash
curl -X POST http://127.0.0.1:8000/api/v1/generate-review ^
  -H "Content-Type: application/json" ^
  -d @examples/generate_review.json
```

### Recommend

```bash
curl -X POST http://127.0.0.1:8000/api/v1/recommend ^
  -H "Content-Type: application/json" ^
  -d @examples/recommend.json
```

### Evaluation

```bash
curl http://127.0.0.1:8000/api/v1/evaluation
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

## Solution Paper

Final paper:

```text
docs/BCT_Solution_Paper_Team_Ace.docx
```

Regenerate it with:

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
app/                  FastAPI app, schemas, services, scoring, LLM clients
static/               Landing page, Task A UI, Task B UI, shared frontend logic
data/fixtures/        Zero-download demo data
data/amazon_subset/   Checked-in real Amazon Reviews 2023 subset
docs/                 Solution paper, screenshots, evaluation report
examples/             Example JSON payloads for API testing
scripts/              Dataset, evaluation, and paper generation scripts
tests/                Unit and integration tests
```

## Team Ace

- **Teslim Sadiq:** product engineering, backend/API integration, deployment, demo flow
- **Yasir Oyebo:** data strategy, evaluation, experiments, model reasoning
- **Abiodun Mark:** UX polish, Nigerian contextualization, storytelling, judge presentation

We are not just submitting an agent. We are demonstrating a practical standard for interpretable, reproducible, and deeply contextual LLM agents built for Nigeria and the world.
