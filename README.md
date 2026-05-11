# BCT LLM Agent Challenge

Containerized FastAPI app for the DSN x BCT hackathon tasks:

- **Task A:** simulate a user's star rating and written review for a product.
- **Task B:** rank personalized cross-domain recommendations for a user persona.

The app uses deterministic local scoring/ranking for reproducibility and Groq for higher-quality generated review text and explanations when `GROQ_API_KEY` is available.

## Quick Start

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`.

## Groq Setup

Create `.env` from `.env.example` and add:

```env
GROQ_API_KEY=your_groq_key
GROQ_MODEL=llama-3.1-8b-instant
```

The app still runs without a Groq key using deterministic fallback generation.

## Docker

```bash
copy .env.example .env
docker compose up --build
```

Then open `http://127.0.0.1:8000`.

## Render Deployment

This repository includes `render.yaml` for one-click Blueprint deployment on Render.

Render settings:

```text
Build Command: pip install -r requirements.txt
Start Command: python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT
Health Check Path: /health
```

Set this secret in the Render dashboard:

```env
GROQ_API_KEY=your_groq_key
YARNGPT_API_KEY=your_yarngpt_key
```

`GROQ_API_KEY` is intentionally marked `sync: false` in `render.yaml`, so the key is never committed to git.

## API

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

### Yarn Mode

`POST /api/v1/yarn` converts a generated review or recommendation explanation into a localized,
voice-ready Nigerian explanation. The UI exposes this as **Yarn Mode** with browser read-aloud.
Available modes include Nigerian Pidgin, Yoruba-flavoured English, Hausa-flavoured English,
Igbo-flavoured English, and a formal judge summary.

When `YARNGPT_API_KEY` is set, `POST /api/v1/yarn-tts` sends the Yarn Mode text to hosted
YarnGPT TTS and returns playable `mp3` audio to the browser. If the key is missing, the UI falls
back to browser speech synthesis.

The UI also supports browser voice input where available:

- Task A: speak product context into the product description field.
- Task B: speak the recommendation context.

Voice input uses the browser Speech Recognition API and falls back to normal typing when unsupported.

## Solution Paper

The paper deliverable is a Word document at `docs/BCT_Solution_Paper.docx`.

Regenerate it with:

```bash
python scripts/create_solution_paper_docx.py
```

## Data Strategy

The checked-in fixture data gives judges a zero-download demo. For the competition run, use Amazon Reviews 2023 categories:

- `Grocery_and_Gourmet_Food`
- `Movies_and_TV`
- `Video_Games`
- `All_Beauty`

`scripts/build_dataset.py` documents the expected conversion flow from downloaded Amazon JSONL files into the app's local fixture shape.

## Evaluation

```bash
pytest
python scripts/evaluate.py
```

The `/api/v1/evaluation` endpoint reports fixture smoke metrics. Larger Amazon subset metrics should be generated with the same split logic after raw data is downloaded.

## Real Amazon Subset

For a stronger competition run, stream a bounded real subset from the official Amazon Reviews 2023 files:

```bash
python scripts/download_amazon_subset.py --max-reviews-per-category 400
```

Then run the app against the generated subset:

```bash
$env:DATA_PATH="data/amazon_subset"
uvicorn app.main:app --reload
```

The script writes `products.json`, `reviews.json`, `splits.json`, and `subset_metrics.json`.

Compare personalized models against baselines:

```bash
python scripts/evaluate_dataset.py --data-path data/amazon_smoke --output docs/evaluation_report.json
```

The current checked-in smoke report shows:

- Task A personalized RMSE: `0.8734` vs global baseline `1.3935`
- Task B personalized NDCG@10: `0.1879` vs popularity baseline `0.0413`
