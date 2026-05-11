from app.schemas import ProductDetails, UserPersona
from app.services.scoring import predict_rating, rank_products, retrieve_evidence


def test_rating_penalizes_low_budget_expensive_item() -> None:
    persona = UserPersona(
        name="Budget user",
        budget_level="low",
        likes=["football", "multiplayer"],
        history=[
            {
                "title": "Football Game",
                "category": "Video_Games",
                "rating": 5,
                "review_text": "fun with friends",
            }
        ],
    )
    cheap = ProductDetails(
        title="Football Arcade",
        category="Video_Games",
        description="Football multiplayer",
        price=10,
    )
    expensive = cheap.model_copy(update={"price": 70})

    cheap_rating, _, _ = predict_rating(persona, cheap, {"average_rating": 4.2, "price": 10})
    expensive_rating, _, _ = predict_rating(
        persona,
        expensive,
        {"average_rating": 4.2, "price": 70},
    )

    assert cheap_rating > expensive_rating


def test_retrieve_evidence_prefers_matching_category() -> None:
    persona = UserPersona(
        history=[
            {
                "title": "Face Cream",
                "category": "All_Beauty",
                "rating": 5,
                "review_text": "gentle on dry skin",
            },
            {
                "title": "Action Movie",
                "category": "Movies_and_TV",
                "rating": 5,
                "review_text": "fast story",
            },
        ]
    )
    product = ProductDetails(
        title="Shea Butter Cream",
        category="All_Beauty",
        description="moisturizing cream for dry skin",
    )
    evidence = retrieve_evidence(persona, product)
    assert evidence[0].category == "All_Beauty"


def test_rank_products_uses_context_and_preferences() -> None:
    persona = UserPersona(interests=["coffee"], likes=["work routines"], budget_level="medium")
    products = [
        {
            "item_id": "1",
            "title": "Ground Coffee",
            "category": "Grocery_and_Gourmet_Food",
            "description": "coffee for morning work",
            "price": 12,
            "average_rating": 4.1,
            "rating_number": 200,
            "attributes": {"keywords": ["coffee"]},
        },
        {
            "item_id": "2",
            "title": "Children Movie",
            "category": "Movies_and_TV",
            "description": "family animation",
            "price": 10,
            "average_rating": 4.8,
            "rating_number": 2000,
            "attributes": {"keywords": ["family"]},
        },
    ]
    ranked = rank_products(persona, products, "morning work drink", [], 2)
    assert ranked[0]["item_id"] == "1"
