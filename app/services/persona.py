from collections import Counter, defaultdict

from app.schemas import ProductDetails, UserPersona
from app.services.text_utils import keyword_set, tokenize


class PersonaSummary:
    def __init__(self, persona: UserPersona):
        self.persona = persona
        self.history_count = len(persona.history)
        self.average_rating = self._average_rating()
        self.category_affinity = self._category_affinity()
        self.keywords = self._keywords()
        self.rating_bias = self.average_rating - 3.8

    def _average_rating(self) -> float:
        if not self.persona.history:
            return 3.8
        return sum(item.rating for item in self.persona.history) / len(self.persona.history)

    def _category_affinity(self) -> dict[str, float]:
        if not self.persona.history:
            return {}
        by_category: dict[str, list[float]] = defaultdict(list)
        for item in self.persona.history:
            by_category[item.category].append(item.rating)
        return {
            category: sum(ratings) / len(ratings)
            for category, ratings in by_category.items()
        }

    def _keywords(self) -> Counter[str]:
        values: list[str] = []
        values.extend(self.persona.interests)
        values.extend(self.persona.likes)
        values.extend(self.persona.dislikes)
        values.extend(
            f"{item.title} {item.category} {item.review_text}" for item in self.persona.history
        )
        values.extend(
            [
                self.persona.location,
                self.persona.occupation,
                self.persona.tone,
                self.persona.cultural_context,
                self.persona.budget_level,
            ]
        )
        return Counter(tokenize(" ".join(values)))

    def preference_tokens(self) -> set[str]:
        return keyword_set(
            self.persona.interests,
            self.persona.likes,
            self.persona.cultural_context,
            self.persona.occupation,
            self.persona.location,
        )

    def dislike_tokens(self) -> set[str]:
        return keyword_set(self.persona.dislikes)

    def describe_for_prompt(self, product: ProductDetails | None = None) -> str:
        history = "; ".join(
            f"{item.title} ({item.category}, {item.rating}/5): {item.review_text}"
            for item in self.persona.history[:6]
        ) or "No explicit purchase history."
        product_line = ""
        if product:
            product_line = (
                f"\nTarget product: {product.title} in {product.category}. "
                f"{product.description}"
            )
        return (
            f"Persona: {self.persona.name}, {self.persona.age_range}, "
            f"{self.persona.occupation}, based in {self.persona.location}. "
            f"Budget: {self.persona.budget_level}. Tone: {self.persona.tone}. "
            f"Likes: {', '.join(self.persona.likes) or 'not provided'}. "
            f"Dislikes: {', '.join(self.persona.dislikes) or 'not provided'}. "
            f"Cultural context: {self.persona.cultural_context}. "
            f"History: {history}.{product_line}"
        )
