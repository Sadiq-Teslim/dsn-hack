from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.schemas import ProductDetails, UserPersona  # noqa: E402
from app.services.scoring import predict_rating, rank_products  # noqa: E402


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def user_persona(user_id: str, train_reviews: list[dict]) -> UserPersona:
    categories = [review["category"] for review in train_reviews]
    interests = sorted(set(categories))[:6]
    history = [
        {
            "title": review["title"],
            "category": review["category"],
            "rating": review["rating"],
            "review_text": review.get("review_text", ""),
        }
        for review in train_reviews[-8:]
    ]
    avg = sum(float(review["rating"]) for review in train_reviews) / max(1, len(train_reviews))
    return UserPersona(
        name=f"Amazon user {user_id[-6:]}",
        location="Nigeria",
        age_range="25-34",
        occupation="Online shopper",
        interests=interests,
        budget_level="medium",
        tone="specific and practical",
        likes=["good value", "clear quality", "reliable products"],
        dislikes=["poor value", "weak performance"],
        cultural_context="Nigerian shopper evaluating imported marketplace products for value and usefulness",
        history=history,
    ).model_copy(update={"_average_hint": avg})


def rmse(errors: list[float]) -> float:
    return round(math.sqrt(sum(error * error for error in errors) / max(1, len(errors))), 4)


def ndcg_at_k(ranked_ids: list[str], target_id: str, k: int) -> float:
    try:
        index = ranked_ids[:k].index(target_id)
    except ValueError:
        return 0.0
    return 1 / math.log2(index + 2)


def evaluate(data_path: Path, output_path: Path | None = None) -> dict:
    products = load_json(data_path / "products.json")
    splits = load_json(data_path / "splits.json")
    product_by_id = {product["item_id"]: product for product in products}
    train_by_user: dict[str, list[dict]] = defaultdict(list)
    for review in splits["train"]:
        train_by_user[review["user_id"]].append(review)

    all_train_ratings = [float(review["rating"]) for review in splits["train"]]
    global_mean = sum(all_train_ratings) / max(1, len(all_train_ratings))
    item_means: dict[str, float] = {}
    item_train: dict[str, list[float]] = defaultdict(list)
    for review in splits["train"]:
        item_train[review["item_id"]].append(float(review["rating"]))
    for item_id, ratings in item_train.items():
        item_means[item_id] = sum(ratings) / len(ratings)

    personalized_errors: list[float] = []
    global_errors: list[float] = []
    item_errors: list[float] = []
    personalized_ndcg: list[float] = []
    popularity_ndcg: list[float] = []
    personalized_hits = 0
    popularity_hits = 0
    evaluated = 0

    popularity_ranked = sorted(products, key=lambda item: (item.get("average_rating", 0), item.get("rating_number", 0)), reverse=True)
    popularity_ids = [item["item_id"] for item in popularity_ranked]

    for held_out in splits["test"]:
        user_history = train_by_user.get(held_out["user_id"], [])
        product_item = product_by_id.get(held_out["item_id"])
        if not user_history or not product_item:
            continue
        persona = user_persona(held_out["user_id"], user_history)
        product = ProductDetails(
            title=product_item["title"],
            category=product_item["category"],
            description=product_item.get("description", ""),
            price=product_item.get("price"),
            brand=product_item.get("brand"),
            attributes=product_item.get("attributes", {}),
        )
        target_rating = float(held_out["rating"])
        prediction, _, _ = predict_rating(persona, product, product_item)
        personalized_errors.append(prediction - target_rating)
        global_errors.append(global_mean - target_rating)
        item_errors.append(item_means.get(held_out["item_id"], global_mean) - target_rating)

        ranked = rank_products(persona, products, held_out["category"], [], 10)
        personalized_ids = [item["item_id"] for item in ranked]
        personalized_ndcg.append(ndcg_at_k(personalized_ids, held_out["item_id"], 10))
        popularity_ndcg.append(ndcg_at_k(popularity_ids, held_out["item_id"], 10))
        personalized_hits += int(held_out["item_id"] in personalized_ids)
        popularity_hits += int(held_out["item_id"] in popularity_ids[:10])
        evaluated += 1

    report = {
        "data_path": str(data_path),
        "evaluated_users": evaluated,
        "task_a": {
            "personalized_rmse": rmse(personalized_errors),
            "global_mean_rmse": rmse(global_errors),
            "item_mean_rmse": rmse(item_errors),
        },
        "task_b": {
            "personalized_ndcg_at_10": round(sum(personalized_ndcg) / max(1, len(personalized_ndcg)), 4),
            "popularity_ndcg_at_10": round(sum(popularity_ndcg) / max(1, len(popularity_ndcg)), 4),
            "personalized_hit_rate_at_10": round(personalized_hits / max(1, evaluated), 4),
            "popularity_hit_rate_at_10": round(popularity_hits / max(1, evaluated), 4),
        },
        "ablations": {
            "rating_lift_vs_global_rmse": round(rmse(global_errors) - rmse(personalized_errors), 4),
            "ranking_lift_vs_popularity_ndcg": round(
                (sum(personalized_ndcg) / max(1, len(personalized_ndcg)))
                - (sum(popularity_ndcg) / max(1, len(popularity_ndcg))),
                4,
            ),
        },
    }
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-path", type=Path, default=Path("data/amazon_smoke"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    print(json.dumps(evaluate(args.data_path, args.output), indent=2))


if __name__ == "__main__":
    main()
