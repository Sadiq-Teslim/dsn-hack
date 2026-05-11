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


def test_recommend_returns_ranked_items() -> None:
    persona = client.get("/api/v1/demo-personas").json()[1]["persona"]
    response = client.post(
        "/api/v1/recommend",
        json={
            "user_persona": persona,
            "context": "weekday routine and a relaxed weekend movie",
            "top_k": 5,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 5
    assert [item["rank"] for item in payload["items"]] == [1, 2, 3, 4, 5]
    assert payload["items"][0]["score"] >= payload["items"][-1]["score"]


def test_fixture_evaluation_metrics() -> None:
    response = client.get("/api/v1/evaluation")
    assert response.status_code == 200
    payload = response.json()
    assert payload["task_a_rmse"] >= 0
    assert 0 <= payload["task_b_ndcg_at_10"] <= 1
