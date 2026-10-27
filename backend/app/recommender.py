import json
import re
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Book, Rating, User

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def _read_neighbors() -> dict[str, list[dict[str, float | str]]]:
    path = Path(settings.neighbors_path)
    if not path.is_absolute():
        path = Path(__file__).parent.parent / path
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as source:
        return json.load(source)


NEIGHBORS = _read_neighbors()


def _tokens(book: Book) -> set[str]:
    text = f"{book.title} {book.author} {book.publisher}".lower()
    return {token for token in TOKEN_PATTERN.findall(text) if len(token) > 2}


def _overlap(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def recommend_books(session: Session, user: User, limit: int = 12) -> list[dict[str, object]]:
    books = list(session.scalars(select(Book)))
    if not books:
        return []

    ratings = list(session.scalars(select(Rating).where(Rating.user_id == user.id)))
    rated_ids = {rating.book_id for rating in ratings}
    positive = [rating for rating in ratings if rating.value >= 4]
    preferred_genres = {value.casefold() for value in user.preferred_genres}
    preferred_authors = {value.casefold() for value in user.preferred_authors}
    max_count = max((book.rating_count for book in books), default=1) or 1
    book_by_id = {book.id: book for book in books}
    own_ratings = {rating.book_id: rating.value for rating in ratings}
    ratings_by_user: dict[str, dict[str, float]] = {}
    for rating in session.scalars(select(Rating).where(Rating.user_id != user.id)):
        ratings_by_user.setdefault(rating.user_id, {})[rating.book_id] = rating.value

    similar_readers: list[tuple[float, dict[str, float]]] = []
    for other_ratings in ratings_by_user.values():
        common_ids = own_ratings.keys() & other_ratings.keys()
        if len(common_ids) < 2:
            continue
        numerator = sum((own_ratings[book_id] - 3) * (other_ratings[book_id] - 3) for book_id in common_ids)
        left_norm = sum((own_ratings[book_id] - 3) ** 2 for book_id in common_ids) ** 0.5
        right_norm = sum((other_ratings[book_id] - 3) ** 2 for book_id in common_ids) ** 0.5
        similarity = numerator / (left_norm * right_norm) if left_norm and right_norm else 0.0
        if similarity > 0.15:
            similar_readers.append((similarity, other_ratings))

    scored: list[dict[str, object]] = []
    for book in books:
        if book.id in rated_ids:
            continue

        reasons: list[str] = []
        item_cf = 0.0
        item_cf_weight = 0.0
        for rating in ratings:
            for neighbor in NEIGHBORS.get(book_by_id[rating.book_id].title, []):
                if str(neighbor["title"]).casefold() == book.title.casefold():
                    similarity = float(neighbor["score"])
                    item_cf += similarity * (rating.value - 3.0) / 2.0
                    item_cf_weight += similarity
        item_cf = item_cf / item_cf_weight if item_cf_weight else 0.0

        reader_score = 0.0
        reader_weight = 0.0
        for similarity, other_ratings in similar_readers:
            if book.id in other_ratings:
                reader_score += similarity * (other_ratings[book.id] - 3.0) / 2.0
                reader_weight += similarity
        reader_score = reader_score / reader_weight if reader_weight else 0.0
        collaborative = max(-1.0, min(1.0, 0.65 * item_cf + 0.35 * reader_score))
        if item_cf > 0.08:
            reasons.append("Matches books you rated highly")
        elif item_cf < -0.08:
            reasons.append("Down-ranked from books you rated lower")
        if reader_score > 0.08:
            reasons.append("Readers with a similar rating pattern enjoyed this")

        content = max(
            (_overlap(_tokens(book), _tokens(book_by_id[rating.book_id])) for rating in positive if rating.book_id in book_by_id),
            default=0.0,
        )
        if content >= 0.18:
            reasons.append("Shares title and author keywords with a favorite")

        matched_genres = preferred_genres.intersection(tag.casefold() for tag in book.genre_tags)
        if matched_genres:
            genre_name = next(tag for tag in book.genre_tags if tag.casefold() in matched_genres)
            reasons.append(f"Fits your {genre_name} preference")
        if book.author.casefold() in preferred_authors:
            reasons.append(f"By an author you follow: {book.author}")

        popularity = book.rating_count / max_count
        preference_score = min(1.0, (len(matched_genres) + int(book.author.casefold() in preferred_authors)) / 2)
        score = 0.52 * collaborative + 0.20 * content + 0.20 * preference_score + 0.08 * popularity

        if not reasons:
            reasons.append("A reader favorite from the catalog")
        scored.append(
            {
                "book": book,
                "score": round(max(0.0, min(1.0, (score + 1.0) / 2.0)), 4),
                "reasons": reasons[:3],
                "model_mix": "collaborative + content + preferences",
            }
        )

    scored.sort(key=lambda item: (float(item["score"]), item["book"].rating_count), reverse=True)
    return scored[:limit]


def catalog_facets(books: list[Book]) -> dict[str, list[str]]:
    genres = sorted({tag for book in books for tag in book.genre_tags})
    authors = sorted({book.author for book in books if book.author})
    return {"genres": genres, "authors": authors}
