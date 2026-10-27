from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models import Book, Rating, User
from app import recommender


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with factory() as db:
        yield db
    engine.dispose()


def _book(book_id: str, title: str, genre: str) -> Book:
    return Book(
        id=book_id,
        title=title,
        author=f"Author {book_id}",
        publisher="Folio Press",
        genre_tags=[genre],
        rating_count=0,
        average_rating=0,
    )


def test_cold_start_uses_genre_preferences(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    session.add_all(
        [
            _book("fantasy", "Dragon at Dusk", "Fantasy"),
            _book("history", "A History of Maps", "History"),
            User(id="reader", preferred_genres=["Fantasy"], preferred_authors=[]),
        ]
    )
    session.commit()
    monkeypatch.setattr(recommender, "NEIGHBORS", {})

    picks = recommender.recommend_books(session, session.get(User, "reader"), 2)

    assert picks[0]["book"].id == "fantasy"
    assert any("Fantasy preference" in reason for reason in picks[0]["reasons"])


def test_similar_readers_can_explain_a_pick(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    session.add_all(
        [
            _book("one", "First Story", "General"),
            _book("two", "Second Story", "General"),
            _book("three", "Third Story", "General"),
            _book("other", "Other Story", "History"),
            User(id="reader", preferred_genres=[], preferred_authors=[]),
            User(id="neighbor", preferred_genres=[], preferred_authors=[]),
        ]
    )
    session.flush()
    session.add_all(
        [
            Rating(user_id="reader", book_id="one", value=5),
            Rating(user_id="reader", book_id="two", value=5),
            Rating(user_id="neighbor", book_id="one", value=5),
            Rating(user_id="neighbor", book_id="two", value=5),
            Rating(user_id="neighbor", book_id="three", value=5),
        ]
    )
    session.commit()
    monkeypatch.setattr(recommender, "NEIGHBORS", {})

    picks = recommender.recommend_books(session, session.get(User, "reader"), 2)

    assert picks[0]["book"].id == "three"
    assert "Readers with a similar rating pattern enjoyed this" in picks[0]["reasons"]
