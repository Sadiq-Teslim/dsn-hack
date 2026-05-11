"""Convert downloaded Amazon Reviews 2023 JSONL files into local app artifacts.

Expected raw layout:
data/raw/
  Grocery_and_Gourmet_Food.reviews.jsonl
  Grocery_and_Gourmet_Food.meta.jsonl
  Movies_and_TV.reviews.jsonl
  Movies_and_TV.meta.jsonl
  ...

This script intentionally avoids downloading the dataset so the repository remains lightweight and
judges can run the fixture app immediately. Download links are documented in the solution paper.
"""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
from typing import Iterable


DEFAULT_CATEGORIES = [
    "Grocery_and_Gourmet_Food",
    "Movies_and_TV",
    "Video_Games",
    "All_Beauty",
]


def read_jsonl(path: Path) -> Iterable[dict]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                yield json.loads(line)


def normalize_product(meta: dict, category: str) -> dict:
    item_id = str(meta.get("parent_asin") or meta.get("asin") or meta.get("item_id"))
    return {
        "item_id": item_id,
        "title": meta.get("title") or "Untitled product",
        "category": category,
        "description": " ".join(meta.get("description") or []) if isinstance(meta.get("description"), list) else meta.get("description", ""),
        "brand": meta.get("brand"),
        "price": _safe_float(meta.get("price")),
        "average_rating": _safe_float(meta.get("average_rating")) or 3.8,
        "rating_number": int(meta.get("rating_number") or 1),
        "attributes": meta.get("details") or {},
    }


def normalize_review(review: dict, category: str, title_by_id: dict[str, str]) -> dict:
    item_id = str(review.get("parent_asin") or review.get("asin") or review.get("item_id"))
    return {
        "user_id": str(review.get("user_id") or review.get("reviewerID") or "unknown"),
        "item_id": item_id,
        "title": title_by_id.get(item_id, review.get("title") or "Untitled product"),
        "category": category,
        "rating": _safe_float(review.get("rating") or review.get("overall")) or 3.0,
        "review_text": review.get("text") or review.get("reviewText") or "",
    }


def _safe_float(value: object) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(str(value).replace("$", "").replace(",", ""))
    except ValueError:
        return None


def build_dataset(raw_dir: Path, output_dir: Path, categories: list[str], max_reviews: int) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    products: list[dict] = []
    reviews: list[dict] = []

    for category in categories:
        meta_path = _first_existing(
            raw_dir / f"{category}.meta.jsonl",
            raw_dir / f"{category}.meta.jsonl.gz",
        )
        review_path = _first_existing(
            raw_dir / f"{category}.reviews.jsonl",
            raw_dir / f"{category}.reviews.jsonl.gz",
        )
        if not meta_path or not review_path:
            print(f"Skipping {category}: missing raw files")
            continue

        category_products = [normalize_product(item, category) for item in read_jsonl(meta_path)]
        title_by_id = {item["item_id"]: item["title"] for item in category_products}
        products.extend(category_products)

        for index, review in enumerate(read_jsonl(review_path)):
            if index >= max_reviews:
                break
            reviews.append(normalize_review(review, category, title_by_id))

    (output_dir / "products.json").write_text(json.dumps(products, indent=2), encoding="utf-8")
    (output_dir / "reviews.json").write_text(json.dumps(reviews, indent=2), encoding="utf-8")
    print(f"Wrote {len(products)} products and {len(reviews)} reviews to {output_dir}")


def _first_existing(*paths: Path) -> Path | None:
    return next((path for path in paths if path.exists()), None)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--categories", nargs="*", default=DEFAULT_CATEGORIES)
    parser.add_argument("--max-reviews-per-category", type=int, default=5000)
    args = parser.parse_args()
    build_dataset(args.raw_dir, args.output_dir, args.categories, args.max_reviews_per_category)


if __name__ == "__main__":
    main()
