import json
import logging
from pathlib import Path

from sqlalchemy import select

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.models import Book

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def seed_catalog() -> int:
    path = Path(settings.catalog_path)
    if not path.is_absolute():
        path = Path(__file__).parent.parent / path
    if not path.exists():
        raise FileNotFoundError(f"Catalog seed file is missing: {path}")

    with path.open(encoding="utf-8") as source:
        rows: list[dict[str, object]] = json.load(source)

    Base.metadata.create_all(bind=engine)
    inserted = 0
    with SessionLocal.begin() as session:
        known_books = {book.id: book for book in session.scalars(select(Book))}
        for row in rows:
            book_id = str(row["id"])
            existing = known_books.get(book_id)
            if existing is None:
                session.add(Book(**row))
                inserted += 1
                continue
            for key, value in row.items():
                if key != "id":
                    setattr(existing, key, value)
    logger.info("Catalog seed complete: %s new books, %s available", inserted, len(rows))
    return inserted


if __name__ == "__main__":
    seed_catalog()
