import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.schemas import DemoPersona, HistoryItem, ProductDetails


class DataStore:
    def __init__(self, data_path: str | Path):
        self.data_path = Path(data_path)
        self.products = self._load_json("products.json")
        self.reviews = self._load_json("reviews.json")
        self.demo_personas = self._load_json("demo_personas.json")

    def _load_json(self, filename: str) -> list[dict[str, Any]]:
        path = self.data_path / filename
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def product_details(self, item: dict[str, Any]) -> ProductDetails:
        return ProductDetails(
            title=item["title"],
            category=item["category"],
            description=item.get("description", ""),
            price=item.get("price"),
            brand=item.get("brand"),
            attributes=item.get("attributes", {}),
        )

    def reviews_for_user(self, user_id: str) -> list[HistoryItem]:
        return [
            HistoryItem(
                title=review["title"],
                category=review["category"],
                rating=review["rating"],
                review_text=review.get("review_text", ""),
            )
            for review in self.reviews
            if review.get("user_id") == user_id
        ]

    def demos(self) -> list[DemoPersona]:
        return [DemoPersona(**item) for item in self.demo_personas]


@lru_cache
def get_data_store() -> DataStore:
    settings = get_settings()
    return DataStore(settings.data_path)
