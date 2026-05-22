from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_reports_local_fallback() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["llm_provider"] == "groq"


def test_demo_personas_are_available() -> None:
    response = client.get("/api/v1/demo-personas")
    assert response.status_code == 200
    personas = response.json()
    assert len(personas) >= 3
    assert personas[0]["persona"]["location"].endswith("Nigeria")


def test_generate_review_uses_fallback_without_groq_key() -> None:
    persona = client.get("/api/v1/demo-personas").json()[0]["persona"]
    product = client.get("/api/v1/products").json()[2]
    response = client.post(
        "/api/v1/generate-review",
        json={
            "user_persona": persona,
            "product": {
                "title": product["title"],
                "category": product["category"],
                "description": product["description"],
                "price": product["price"],
                "brand": product["brand"],
                "attributes": product["attributes"],
            },
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert 1 <= payload["rating"] <= 5
    assert payload["review_text"]
    assert payload["fallback_used"] is True
    assert payload["evidence"]
    assert payload["evidence"][0]["source"] in {"own_history", "similar_user"}
    assert payload["evidence"][0]["retrieval_score"] is not None
    assert [step["name"] for step in payload["reasoning_trace"]["steps"]] == [
        "ResolveUserProfileStep",
        "RetrieveEvidenceStep",
        "PredictSentimentStep",
        "CalibrateRatingStep",
        "GenerateReviewStep",
        "ConsistencyCheckStep",
        "FormalizeReviewReasoningStep",
    ]
    assert payload["calibration"]["calibrated_rating"] == payload["rating"]


def test_recommend_returns_ranked_items() -> None:
    persona = client.get("/api/v1/demo-personas").json()[1]["persona"]
    response = client.post(
        "/api/v1/recommend",
        json={
            "user_persona": persona,
            "context": "weekday routine and a relaxed weekend movie",
            "top_k": 3,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 3
    assert [item["rank"] for item in payload["items"]] == [1, 2, 3]
    assert payload["items"][0]["score"] >= payload["items"][-1]["score"]
    assert "LLMRerankStep" in [step["name"] for step in payload["reasoning_trace"]["steps"]]
    visible_text = " ".join(
        [payload["reasoning"], *[item["reason"] for item in payload["items"]]]
    ).lower()
    assert "llm" not in visible_text
    assert "retrieval" not in visible_text
    assert "candidate" not in visible_text
    assert "catalog" not in visible_text
    assert payload["session_id"]


def test_cross_domain_recommendation_prioritizes_target_domain() -> None:
    persona = client.get("/api/v1/demo-personas").json()[0]["persona"]
    response = client.post(
        "/api/v1/recommend",
        json={
            "user_persona": persona,
            "context": "based on my movie taste, recommend me food for the weekend",
            "include_categories": ["Grocery_and_Gourmet_Food"],
            "top_k": 3,
            "conversational": True,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert {item["category"] for item in payload["items"]} == {"Grocery_and_Gourmet_Food"}
    bridge = next(step for step in payload["reasoning_trace"]["steps"] if step["name"] == "CrossDomainBridgeStep")
    assert bridge["outputs"]["is_cross_domain"] is True


def test_book_query_returns_books_instead_of_movies() -> None:
    persona = client.get("/api/v1/demo-personas").json()[0]["persona"]
    response = client.post(
        "/api/v1/recommend",
        json={
            "user_persona": persona,
            "context": "I want to buy five books.",
            "top_k": 5,
            "conversational": True,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 5
    assert {item["category"] for item in payload["items"]} == {"Books"}
    assert "Wedding Party" not in {item["title"] for item in payload["items"]}


def test_book_query_respects_explicit_price_ceiling() -> None:
    persona = client.get("/api/v1/demo-personas").json()[0]["persona"]
    response = client.post(
        "/api/v1/recommend",
        json={
            "user_persona": persona,
            "context": "I want books below $10 only.",
            "top_k": 8,
            "conversational": True,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["items"]
    assert {item["category"] for item in payload["items"]} == {"Books"}
    assert all(item["price"] < 10 for item in payload["items"])
    shortlist = next(step for step in payload["reasoning_trace"]["steps"] if step["name"] == "CandidateShortlistStep")
    assert shortlist["outputs"]["max_price"] == 10.0


def test_weekly_utility_query_prioritizes_practical_categories() -> None:
    persona = client.get("/api/v1/demo-personas").json()[0]["persona"]
    response = client.post(
        "/api/v1/recommend",
        json={
            "user_persona": persona,
            "context": "I want useful options for this week that fit my budget and routine.",
            "top_k": 5,
            "conversational": True,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    categories = [item["category"] for item in payload["items"]]
    assert categories[0] in {"Grocery_and_Gourmet_Food", "All_Beauty"}
    assert "Movies_and_TV" not in categories[:2]


def test_fixture_evaluation_metrics() -> None:
    response = client.get("/api/v1/evaluation")
    assert response.status_code == 200
    payload = response.json()
    assert payload["task_a_rmse"] >= 0
    assert 0 <= payload["task_b_ndcg_at_10"] <= 1


def test_yarn_mode_endpoint_returns_voice_script() -> None:
    persona = client.get("/api/v1/demo-personas").json()[0]["persona"]
    response = client.post(
        "/api/v1/yarn",
        json={
            "user_persona": persona,
            "source_text": "The product scored 4.7 because it fits the user's taste and budget.",
            "mode": "Nigerian Pidgin",
            "task": "review",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["voice_script"]
    assert payload["judge_note"]
    assert payload["mode"] == "Nigerian Pidgin"


def test_yarngpt_tts_falls_back_without_key() -> None:
    response = client.post(
        "/api/v1/yarn-tts",
        json={
            "text": "This is a short local voice test.",
            "voice": "Idera",
            "response_format": "mp3",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["audio_data_url"] is None
    assert payload["fallback_used"] is True
    assert payload["voice"] == "Idera"
