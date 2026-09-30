import os
from pathlib import Path

TEST_DB = Path(__file__).with_name(".test_fitbuddy.sqlite3")
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ.pop("GEMINI_API_KEY", None)
os.environ.pop("GOOGLE_API_KEY", None)

from fastapi.testclient import TestClient  # noqa: E402
import pytest  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture()
def client():
    # Using TestClient as a context manager runs the FastAPI lifespan hook,
    # which creates the SQLite tables before the first request.
    with TestClient(app) as test_client:
        yield test_client


def test_health_and_homepage(client):
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    page = client.get("/")
    assert page.status_code == 200
    assert "Your fitness snapshot" in page.text


def test_api_generation_feedback_and_admin_view(client):
    payload = {
        "name": "Test Runner",
        "user_id": "test-runner-1",
        "age": 29,
        "weight_kg": 72,
        "goal": "muscle gain",
        "intensity": "medium",
    }
    generated = client.post("/api/plans/generate", json=payload)
    assert generated.status_code == 201
    body = generated.json()
    assert body["user"]["user_id"] == "test-runner-1"
    assert "Day 1" in body["original_plan"]
    assert body["ai_source"] == "fallback"

    updated = client.post(
        "/api/plans/test-runner-1/feedback",
        json={"user_id": "test-runner-1", "feedback": "Please add one more recovery day."},
    )
    assert updated.status_code == 200
    assert updated.json()["feedback_count"] == 1
    assert "recovery day" in updated.json()["updated_plan"]

    admin = client.get("/api/users")
    assert admin.status_code == 200
    assert any(item["user"]["user_id"] == "test-runner-1" for item in admin.json())


def test_html_generation_and_validation(client):
    response = client.post(
        "/generate-workout",
        data={
            "name": "HTML Runner",
            "user_id": "html-runner-1",
            "age": "34",
            "weight_kg": "68",
            "goal": "weight loss",
            "intensity": "low",
        },
    )
    assert response.status_code == 200
    assert "Seven-day movement map" in response.text
    assert "HTML Runner" in response.text

    invalid = client.post(
        "/api/plans/generate",
        json={"name": "x", "user_id": "bad id", "age": 5, "weight_kg": 2, "goal": "unknown", "intensity": "high"},
    )
    assert invalid.status_code == 422
