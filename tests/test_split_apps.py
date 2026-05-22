from fastapi.testclient import TestClient

from app.task_a_main import app as task_a_app
from app.task_b_main import app as task_b_app


task_a_client = TestClient(task_a_app)
task_b_client = TestClient(task_b_app)


def test_task_a_app_serves_review_workspace_only() -> None:
    health = task_a_client.get("/health")
    assert health.status_code == 200
    assert "Task A" in health.json()["app"]

    page = task_a_client.get("/")
    assert page.status_code == 200
    assert "Generate Review" in page.text

    assert task_a_client.post("/api/v1/recommend", json={}).status_code == 404


def test_task_b_app_serves_recommendation_workspace_only() -> None:
    health = task_b_client.get("/health")
    assert health.status_code == 200
    assert "Task B" in health.json()["app"]

    page = task_b_client.get("/")
    assert page.status_code == 200
    assert "Chat message" in page.text
    assert "Recommendation agent" in page.text

    assert task_b_client.post("/api/v1/generate-review", json={}).status_code == 404
