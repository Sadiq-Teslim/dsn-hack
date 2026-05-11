"""Stream a bounded real Amazon Reviews 2023 subset into the app schema.

The official files are large, so this script reads only enough lines to build a reproducible
competition-sized sample. It does not commit raw downloads; it writes normalized JSON artifacts
that can be used by setting DATA_PATH=data/amazon_subset.
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterable
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DEFAULT = ROOT / "data" / "amazon_subset"

AMAZON_2023_URLS = {
    "All_Beauty": {
        "review": "https://mcauleylab.ucsd.edu/public_datasets/data/amazon_2023/raw/review_categories/All_Beauty.jsonl.gz",
        "meta": "https://mcauleylab.ucsd.edu/public_datasets/data/amazon_2023/raw/meta_categories/meta_All_Beauty.jsonl.gz",
    },
    "Grocery_and_Gourmet_Food": {
        "review": "https://mcauleylab.ucsd.edu/public_datasets/data/amazon_2023/raw/review_categories/Grocery_and_Gourmet_Food.jsonl.gz",
        "meta": "https://mcauleylab.ucsd.edu/public_datasets/data/amazon_2023/raw/meta_categories/meta_Grocery_and_Gourmet_Food.jsonl.gz",
    },
    "Movies_and_TV": {
        "review": "https://mcauleylab.ucsd.edu/public_datasets/data/amazon_2023/raw/review_categories/Movies_and_TV.jsonl.gz",
        "meta": "https://mcauleylab.ucsd.edu/public_datasets/data/amazon_2023/raw/meta_categories/meta_Movies_and_TV.jsonl.gz",
    },
    "Video_Games": {
        "review": "https://mcauleylab.ucsd.edu/public_datasets/data/amazon_2023/raw/review_categories/Video_Games.jsonl.gz",
        "meta": "https://mcauleylab.ucsd.edu/public_datasets/data/amazon_2023/raw/meta_categories/meta_Video_Games.jsonl.gz",
    },
}


def stream_jsonl_gz(url: str, limit: int | None = None) -> Iterable[dict]:
    request = Request(url, headers={"User-Agent": "bct-agent-subset/0.1"})
    with urlopen(request, timeout=90) as response:
        with gzip.GzipFile(fileobj=response) as gz:
            for index, raw_line in enumerate(gz):
                if limit is not None and index >= limit:
                    break
                line = raw_line.decode("utf-8", errors="ignore").strip()
                if line:
                    yield json.loads(line)


def safe_float(value: object, default: float | None = None) -> float | None:
    try:
        if value in (None, "", "None"):
            return default
        return float(str(value).replace("$", "").replace(",", ""))
    except ValueError:
        return default


def normalize_review(raw: dict, category: str) -> dict:
    item_id = str(raw.get("parent_asin") or raw.get("asin") or "")
    return {
        "user_id": str(raw.get("user_id") or "unknown"),
        "item_id": item_id,
        "title": raw.get("title") or "Untitled review",
        "category": category,
        "rating": safe_float(raw.get("rating"), 3.0) or 3.0,
        "review_text": raw.get("text") or "",
        "timestamp": int(raw.get("sort_timestamp") or 0),
    }


def normalize_product(raw: dict, category: str, review_stats: dict[str, list[float]]) -> dict:
    item_id = str(raw.get("parent_asin") or raw.get("asin") or "")
    features = raw.get("features") or []
    description = raw.get("description") or []
    if isinstance(description, list):
        description_text = " ".join(str(item) for item in description[:4])
    else:
        description_text = str(description or "")
    if not description_text and features:
        description_text = " ".join(str(item) for item in features[:3])

    stats = review_stats.get(item_id, [])
    average = sum(stats) / len(stats) if stats else safe_float(raw.get("average_rating"), 3.8)
    return {
        "item_id": item_id,
        "title": raw.get("title") or "Untitled product",
        "category": category,
        "description": description_text[:900],
        "brand": raw.get("brand") or raw.get("store"),
        "price": safe_float(raw.get("price")),
        "average_rating": round(float(average or 3.8), 3),
        "rating_number": int(raw.get("rating_number") or len(stats) or 1),
        "attributes": {
            "main_category": raw.get("main_category"),
            "features": features[:5],
            "details": raw.get("details") or {},
            "keywords": _keywords(raw.get("title"), description_text, features),
        },
    }


def _keywords(*parts: object) -> list[str]:
    text = " ".join(
        " ".join(str(value) for value in part) if isinstance(part, list) else str(part or "")
        for part in parts
    )
    tokens = [
        token.lower().strip(".,:;!?()[]{}")
        for token in text.split()
        if len(token.strip(".,:;!?()[]{}")) > 3
    ]
    seen: set[str] = set()
    output: list[str] = []
    for token in tokens:
        if token not in seen:
            seen.add(token)
            output.append(token)
        if len(output) >= 12:
            break
    return output


def select_reviews(raw_reviews: Iterable[dict], category: str, max_reviews: int, min_text_chars: int) -> list[dict]:
    by_user: dict[str, list[dict]] = defaultdict(list)
    for raw in raw_reviews:
        review = normalize_review(raw, category)
        if not review["item_id"] or len(review["review_text"]) < min_text_chars:
            continue
        by_user[review["user_id"]].append(review)
        if sum(len(items) for items in by_user.values()) >= max_reviews * 3:
            break

    balanced: list[dict] = []
    for user_reviews in by_user.values():
        if len(user_reviews) < 2:
            continue
        user_reviews.sort(key=lambda item: item["timestamp"])
        balanced.extend(user_reviews[-4:])
        if len(balanced) >= max_reviews:
            break
    return balanced[:max_reviews]


def build_subset(categories: list[str], output_dir: Path, max_reviews_per_category: int, meta_scan_limit: int, min_text_chars: int) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    all_reviews: list[dict] = []
    all_products: list[dict] = []
    splits: dict[str, list[dict]] = {"train": [], "test": []}

    for category in categories:
        urls = AMAZON_2023_URLS[category]
        print(f"Streaming reviews for {category}...", flush=True)
        reviews = select_reviews(
            stream_jsonl_gz(urls["review"]),
            category,
            max_reviews=max_reviews_per_category,
            min_text_chars=min_text_chars,
        )
        wanted_items = {review["item_id"] for review in reviews}
        review_stats: dict[str, list[float]] = defaultdict(list)
        for review in reviews:
            review_stats[review["item_id"]].append(float(review["rating"]))

        print(f"Streaming metadata for {category} ({len(wanted_items)} wanted items)...", flush=True)
        products: list[dict] = []
        for raw_meta in stream_jsonl_gz(urls["meta"], limit=meta_scan_limit):
            item_id = str(raw_meta.get("parent_asin") or raw_meta.get("asin") or "")
            if item_id in wanted_items:
                products.append(normalize_product(raw_meta, category, review_stats))
                if len(products) >= len(wanted_items):
                    break

        title_by_id = {product["item_id"]: product["title"] for product in products}
        for review in reviews:
            if title_by_id.get(review["item_id"]):
                review["title"] = title_by_id[review["item_id"]]

        train, test = chronological_user_split(reviews)
        splits["train"].extend(train)
        splits["test"].extend(test)
        all_reviews.extend(reviews)
        all_products.extend(products)

    metrics = summarize_subset(all_products, all_reviews, splits)
    write_json(output_dir / "products.json", all_products)
    write_json(output_dir / "reviews.json", all_reviews)
    write_json(output_dir / "splits.json", splits)
    write_json(output_dir / "subset_metrics.json", metrics)
    return metrics


def chronological_user_split(reviews: list[dict]) -> tuple[list[dict], list[dict]]:
    by_user: dict[str, list[dict]] = defaultdict(list)
    for review in reviews:
        by_user[review["user_id"]].append(review)
    train: list[dict] = []
    test: list[dict] = []
    for user_reviews in by_user.values():
        user_reviews.sort(key=lambda item: item.get("timestamp", 0))
        if len(user_reviews) >= 2:
            train.extend(user_reviews[:-1])
            test.append(user_reviews[-1])
        else:
            train.extend(user_reviews)
    return train, test


def summarize_subset(products: list[dict], reviews: list[dict], splits: dict[str, list[dict]]) -> dict:
    categories = sorted({item["category"] for item in products} | {item["category"] for item in reviews})
    ratings = [float(review["rating"]) for review in reviews]
    average_rating = sum(ratings) / len(ratings) if ratings else 0
    category_counts = {
        category: {
            "products": sum(1 for item in products if item["category"] == category),
            "reviews": sum(1 for item in reviews if item["category"] == category),
        }
        for category in categories
    }
    return {
        "source": "Amazon Reviews 2023 official McAuley Lab JSONL.GZ files",
        "categories": categories,
        "products": len(products),
        "reviews": len(reviews),
        "users": len({review["user_id"] for review in reviews}),
        "average_rating": round(average_rating, 3),
        "train_interactions": len(splits["train"]),
        "test_interactions": len(splits["test"]),
        "category_counts": category_counts,
        "rmse_baseline_estimate": round(math.sqrt(sum((rating - average_rating) ** 2 for rating in ratings) / max(1, len(ratings))), 3),
    }


def write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--categories", nargs="*", default=list(AMAZON_2023_URLS))
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DEFAULT)
    parser.add_argument("--max-reviews-per-category", type=int, default=400)
    parser.add_argument("--meta-scan-limit", type=int, default=250000)
    parser.add_argument("--min-text-chars", type=int, default=60)
    args = parser.parse_args()

    invalid = sorted(set(args.categories) - set(AMAZON_2023_URLS))
    if invalid:
        print(f"Unknown categories: {', '.join(invalid)}", file=sys.stderr)
        sys.exit(2)
    metrics = build_subset(
        args.categories,
        args.output_dir,
        args.max_reviews_per_category,
        args.meta_scan_limit,
        args.min_text_chars,
    )
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
