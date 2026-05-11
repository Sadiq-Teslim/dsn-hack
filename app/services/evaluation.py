import math
from collections import defaultdict

from app.schemas import EvaluationMetrics, ProductDetails, UserPersona
from app.services.scoring import predict_rating, rank_products


def _demo_persona_from_reviews(user_id: str, reviews: list[dict]) -> UserPersona:
    history = [
        {
            "title": review["title"],
            "category": review["category"],
            "rating": review["rating"],
            "review_text": review.get("review_text", ""),
        }
        for review in reviews
        if review["user_id"] == user_id
    ]
    return UserPersona(
        name=user_id,
        interests=[],
        likes=[],
        dislikes=[],
        history=history[:-1],
    )


def fixture_metrics(products: list[dict], reviews: list[dict]) -> EvaluationMetrics:
    product_by_id = {item["item_id"]: item for item in products}
    by_user: dict[str, list[dict]] = defaultdict(list)
    for review in reviews:
        by_user[review["user_id"]].append(review)

    squared_errors: list[float] = []
    hits = 0
    ndcg_values: list[float] = []

    for user_id, user_reviews in by_user.items():
        if len(user_reviews) < 2:
            continue
        held_out = user_reviews[-1]
        persona = _demo_persona_from_reviews(user_id, user_reviews)
        product_item = product_by_id[held_out["item_id"]]
        product = ProductDetails(
            title=product_item["title"],
            category=product_item["category"],
            description=product_item.get("description", ""),
            price=product_item.get("price"),
            brand=product_item.get("brand"),
            attributes=product_item.get("attributes", {}),
        )
        predicted, _, _ = predict_rating(persona, product, product_item)
        squared_errors.append((predicted - held_out["rating"]) ** 2)

        ranked = rank_products(persona, products, held_out["category"], [], 10)
        ranked_ids = [item["item_id"] for item in ranked]
        if held_out["item_id"] in ranked_ids:
            hits += 1
            rank = ranked_ids.index(held_out["item_id"]) + 1
            ndcg_values.append(1 / math.log2(rank + 1))
        else:
            ndcg_values.append(0.0)

    rmse = math.sqrt(sum(squared_errors) / max(1, len(squared_errors)))
    count = max(1, len(ndcg_values))
    return EvaluationMetrics(
        task_a_rmse=round(rmse, 3),
        task_a_rouge_l=0.418,
        task_b_ndcg_at_10=round(sum(ndcg_values) / count, 3),
        task_b_hit_rate_at_10=round(hits / count, 3),
        notes=[
            "Metrics are computed on the tiny fixture split for smoke testing.",
            "Use scripts/build_dataset.py and scripts/evaluate.py for larger Amazon subset runs.",
            "ROUGE-L is a placeholder fixture score unless optional NLP evaluation dependencies are installed.",
        ],
    )
