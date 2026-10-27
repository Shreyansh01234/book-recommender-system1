from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Book


@pytest.fixture
def api_client() -> Iterator[TestClient]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    test_sessions = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_get_db():
        with test_sessions() as session:
            yield session

    with test_sessions.begin() as session:
        session.add_all(
            [
                Book(id="read", title="Already Read", author="A. Reader", publisher="Folio", genre_tags=["General"]),
                Book(id="pick-one", title="A New Story", author="A. Writer", publisher="Folio", genre_tags=["Fantasy"]),
                Book(id="pick-two", title="Another Story", author="B. Writer", publisher="Folio", genre_tags=["Mystery"]),
            ]
        )

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_reader_rating_history_and_recommendation_round_trip(api_client: TestClient) -> None:
    user = api_client.post("/api/v1/users", json={"id": "test-reader", "display_name": "Test Reader"})
    assert user.status_code == 201

    preferences = api_client.put(
        "/api/v1/users/test-reader/preferences",
        json={"preferred_genres": ["Fantasy"], "preferred_authors": []},
    )
    assert preferences.status_code == 200
    assert preferences.json()["preferred_genres"] == ["Fantasy"]

    rating_payload = {"user_id": "test-reader", "book_id": "read", "value": 5}
    assert api_client.post("/api/v1/ratings", json=rating_payload).status_code == 200
    rating_payload["value"] = 4
    assert api_client.post("/api/v1/ratings", json=rating_payload).status_code == 200

    history = api_client.get("/api/v1/users/test-reader/history")
    picks = api_client.get("/api/v1/recommendations?user_id=test-reader&limit=2")
    assert history.status_code == 200
    assert len(history.json()) == 1
    assert history.json()[0]["value"] == 4
    assert picks.status_code == 200
    assert len(picks.json()) == 2
    assert all(item["book"]["id"] != "read" and item["reasons"] for item in picks.json())
