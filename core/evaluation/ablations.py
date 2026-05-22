from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from app.config import Settings
from app.schemas import ProductDetails, UserPersona
from app.services.scoring import rank_products
from core.evaluation.metrics import ndcg_at_k, rmse, rouge_l_f1
from core.task_a import run_task_a_pipeline
from core.task_b import run_task_b_pipeline


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def persona_from_reviews(user_id: str, train_reviews: list[dict[str, Any]]) -> UserPersona:
    categories = [review["category"] for review in train_reviews]
    history = [
        {
            "title": review["title"],
            "category": review["category"],
            "rating": review["rating"],
            "review_text": review.get("review_text", ""),
        }
        for review in train_reviews[-8:]
    ]
    return UserPersona(
        name=f"Amazon user {user_id[-6:]}",
        location="Lagos, Nigeria",
        age_range="25-34",
        occupation="Online shopper",
        interests=sorted(set(categories))[:6],
        budget_level="medium",
        tone="specific and practical",
        likes=["good value", "clear quality", "reliable products"],
        dislikes=["poor value", "weak performance"],
        language_preference="English",
        cultural_context="Nigerian shopper evaluating imported marketplace products for value and usefulness",
        history=history,
    )


async def evaluate_agent_dataset(
    data_path: Path,
    output_path: Path | None = None,
    max_examples: int = 100,
    require_llm: bool = False,
) -> dict[str, Any]:
    products = load_json(data_path / "products.json")
    splits = load_json(data_path / "splits.json")
    product_by_id = {product["item_id"]: product for product in products}
    train_by_user: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for review in splits["train"]:
        train_by_user[review["user_id"]].append(review)

    all_train_ratings = [float(review["rating"]) for review in splits["train"]]
    global_mean = sum(all_train_ratings) / max(1, len(all_train_ratings))
    item_train: dict[str, list[float]] = defaultdict(list)
    for review in splits["train"]:
        item_train[review["item_id"]].append(float(review["rating"]))
    item_means = {
        item_id: sum(ratings) / len(ratings)
        for item_id, ratings in item_train.items()
    }
    popularity_ids = [
        item["item_id"]
        for item in sorted(
            products,
            key=lambda item: (item.get("average_rating", 0), item.get("rating_number", 0)),
            reverse=True,
        )
    ]

    settings = Settings(llm_timeout_seconds=30.0)
    if require_llm and not settings.groq_api_key:
        raise RuntimeError("GROQ_API_KEY is required for this evaluation run.")
    full_errors: list[float] = []
    raw_errors: list[float] = []
    global_errors: list[float] = []
    item_errors: list[float] = []
    rouge_scores: list[float] = []
    full_ndcg: list[float] = []
    local_ndcg: list[float] = []
    popularity_ndcg: list[float] = []
    full_hits = 0
    local_hits = 0
    popularity_hits = 0
    evaluated = 0
    examples: list[dict[str, Any]] = []
    task_a_fallbacks = 0
    task_b_fallbacks = 0

    for held_out in splits["test"][:max_examples]:
        train_reviews = train_by_user.get(held_out["user_id"], [])
        product_item = product_by_id.get(held_out["item_id"])
        if not train_reviews or not product_item:
            continue
        persona = persona_from_reviews(held_out["user_id"], train_reviews)
        product = ProductDetails(
            title=product_item["title"],
            category=product_item["category"],
            description=product_item.get("description", ""),
            price=product_item.get("price"),
            brand=product_item.get("brand"),
            attributes=product_item.get("attributes", {}),
        )
        target_rating = float(held_out["rating"])
        task_a = await _run_task_a_with_eval_retries(
            settings,
            persona,
            product,
            products,
            splits["train"],
            require_llm=require_llm,
        )
        task_a_fallbacks += int(task_a.fallback_used)
        full_errors.append(task_a.rating - target_rating)
        raw_errors.append(task_a.calibration.raw_rating - target_rating)
        global_errors.append(global_mean - target_rating)
        item_errors.append(item_means.get(held_out["item_id"], global_mean) - target_rating)
        rouge_scores.append(rouge_l_f1(task_a.review_text, held_out.get("review_text", "")))

        task_b = await _run_task_b_with_eval_retries(
            settings,
            persona,
            products,
            f"Recommend a {held_out['category'].replace('_', ' ')} item that fits my history.",
            [held_out["category"]],
            require_llm=require_llm,
        )
        task_b_fallbacks += int(task_b.fallback_used)
        full_ids = [item.item_id for item in task_b.items]
        local_ranked = rank_products(persona, products, held_out["category"], [], 10)
        local_ids = [item["item_id"] for item in local_ranked]

        full_ndcg.append(ndcg_at_k(full_ids, held_out["item_id"], 10))
        local_ndcg.append(ndcg_at_k(local_ids, held_out["item_id"], 10))
        popularity_ndcg.append(ndcg_at_k(popularity_ids, held_out["item_id"], 10))
        full_hits += int(held_out["item_id"] in full_ids)
        local_hits += int(held_out["item_id"] in local_ids)
        popularity_hits += int(held_out["item_id"] in popularity_ids[:10])
        evaluated += 1

        if len(examples) < 5:
            examples.append(
                {
                    "user_id": held_out["user_id"],
                    "target_item": held_out["title"],
                    "target_rating": target_rating,
                    "predicted_rating": task_a.rating,
                    "generated_review": task_a.review_text,
                    "top_recommendations": [item.title for item in task_b.items[:3]],
                }
            )
        if evaluated % 5 == 0:
            print(
                f"evaluated={evaluated} task_a_fallbacks={task_a_fallbacks} task_b_fallbacks={task_b_fallbacks}",
                flush=True,
            )

    report = {
        "data_path": str(data_path),
        "evaluated_examples": evaluated,
        "task_a": {
            "agent_rmse": rmse(full_errors),
            "no_calibration_raw_rmse": rmse(raw_errors),
            "global_mean_rmse": rmse(global_errors),
            "item_mean_rmse": rmse(item_errors),
            "rouge_l_f1": round(sum(rouge_scores) / max(1, len(rouge_scores)), 4),
            "llm_fallback_count": task_a_fallbacks,
        },
        "task_b": {
            "agent_ndcg_at_10": round(sum(full_ndcg) / max(1, len(full_ndcg)), 4),
            "local_ranker_ndcg_at_10": round(sum(local_ndcg) / max(1, len(local_ndcg)), 4),
            "popularity_ndcg_at_10": round(sum(popularity_ndcg) / max(1, len(popularity_ndcg)), 4),
            "agent_hit_rate_at_10": round(full_hits / max(1, evaluated), 4),
            "local_ranker_hit_rate_at_10": round(local_hits / max(1, evaluated), 4),
            "popularity_hit_rate_at_10": round(popularity_hits / max(1, evaluated), 4),
            "llm_fallback_count": task_b_fallbacks,
        },
        "ablations": {
            "calibration_rmse_lift_vs_raw": round(rmse(raw_errors) - rmse(full_errors), 4),
            "agent_rmse_lift_vs_global": round(rmse(global_errors) - rmse(full_errors), 4),
            "agent_ndcg_lift_vs_local": round(
                (sum(full_ndcg) / max(1, len(full_ndcg)))
                - (sum(local_ndcg) / max(1, len(local_ndcg))),
                4,
            ),
            "agent_ndcg_lift_vs_popularity": round(
                (sum(full_ndcg) / max(1, len(full_ndcg)))
                - (sum(popularity_ndcg) / max(1, len(popularity_ndcg))),
                4,
            ),
        },
        "examples": examples,
        "llm_configured": bool(settings.groq_api_key),
    }
    if require_llm and (task_a_fallbacks or task_b_fallbacks):
        raise RuntimeError(
            f"LLM-required evaluation used fallback text: task_a={task_a_fallbacks}, task_b={task_b_fallbacks}."
        )
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def evaluate_agent_dataset_sync(
    data_path: Path,
    output_path: Path | None = None,
    max_examples: int = 100,
    require_llm: bool = False,
) -> dict[str, Any]:
    return asyncio.run(evaluate_agent_dataset(data_path, output_path, max_examples, require_llm))


async def _run_task_a_with_eval_retries(
    settings: Settings,
    persona: UserPersona,
    product: ProductDetails,
    products: list[dict[str, Any]],
    reviews: list[dict[str, Any]],
    require_llm: bool,
):
    attempts = 4 if require_llm else 1
    result = None
    for _ in range(attempts):
        result = await run_task_a_pipeline(settings, persona, product, products, reviews)
        if not require_llm or not result.fallback_used:
            return result
    return result


async def _run_task_b_with_eval_retries(
    settings: Settings,
    persona: UserPersona,
    products: list[dict[str, Any]],
    context: str,
    categories: list[str],
    require_llm: bool,
):
    attempts = 4 if require_llm else 1
    result = None
    for _ in range(attempts):
        result = await run_task_b_pipeline(
            settings,
            persona,
            products,
            context,
            categories,
            10,
            conversational=False,
        )
        if not require_llm or not result.fallback_used:
            return result
    return result
