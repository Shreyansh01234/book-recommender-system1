from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.database import Base, engine, get_db
from app.models import Book, Rating, User
from app.recommender import catalog_facets, recommend_books
from app.schemas import (
    BookOut,
    PreferencesUpdate,
    RatingCreate,
    RatingOut,
    RecommendationOut,
    UserCreate,
    UserOut,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Folio Book Discovery API",
    description="A hybrid book discovery API with persisted reader preferences and ratings.",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/books", response_model=list[BookOut])
def search_books(
    query: str = Query(default="", max_length=120),
    genre: str | None = Query(default=None, max_length=80),
    author: str | None = Query(default=None, max_length=160),
    limit: int = Query(default=24, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_db),
) -> list[Book]:
    statement = select(Book).order_by(Book.rating_count.desc(), Book.title.asc())
    books = list(session.scalars(statement))
    normalized_query = query.casefold().strip()
    normalized_genre = genre.casefold().strip() if genre else ""
    normalized_author = author.casefold().strip() if author else ""
    matches = [
        book
        for book in books
        if (not normalized_query or normalized_query in f"{book.title} {book.author}".casefold())
        and (not normalized_genre or normalized_genre in {tag.casefold() for tag in book.genre_tags})
        and (not normalized_author or normalized_author in book.author.casefold())
    ]
    return matches[offset : offset + limit]


@app.get("/api/v1/books/facets")
def get_facets(session: Session = Depends(get_db)) -> dict[str, list[str]]:
    books = list(session.scalars(select(Book)))
    return catalog_facets(books)


@app.post("/api/v1/users", response_model=UserOut, status_code=201)
def create_user(payload: UserCreate, session: Session = Depends(get_db)) -> User:
    existing = session.get(User, payload.id)
    if existing:
        return existing
    user = User(**payload.model_dump())
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@app.get("/api/v1/users/{user_id}", response_model=UserOut)
def get_user(user_id: str, session: Session = Depends(get_db)) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Reader profile not found")
    return user


@app.put("/api/v1/users/{user_id}/preferences", response_model=UserOut)
def update_preferences(
    user_id: str,
    payload: PreferencesUpdate,
    session: Session = Depends(get_db),
) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Reader profile not found")
    user.preferred_genres = payload.preferred_genres
    user.preferred_authors = payload.preferred_authors
    session.commit()
    session.refresh(user)
    return user


@app.get("/api/v1/users/{user_id}/history", response_model=list[RatingOut])
def get_history(user_id: str, session: Session = Depends(get_db)) -> list[Rating]:
    if session.get(User, user_id) is None:
        raise HTTPException(status_code=404, detail="Reader profile not found")
    return list(
        session.scalars(
            select(Rating)
            .where(Rating.user_id == user_id)
            .order_by(Rating.created_at.desc())
            .options(joinedload(Rating.book))
        )
    )


@app.get("/api/v1/recommendations", response_model=list[RecommendationOut])
def get_recommendations(
    user_id: str,
    limit: int = Query(default=12, ge=1, le=40),
    session: Session = Depends(get_db),
) -> list[dict[str, object]]:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Reader profile not found")
    return recommend_books(session, user, limit)


@app.post("/api/v1/ratings", response_model=RatingOut)
def save_rating(payload: RatingCreate, session: Session = Depends(get_db)) -> Rating:
    if session.get(User, payload.user_id) is None:
        raise HTTPException(status_code=404, detail="Reader profile not found")
    if session.get(Book, payload.book_id) is None:
        raise HTTPException(status_code=404, detail="Book not found")
    rating = session.scalar(
        select(Rating).where(Rating.user_id == payload.user_id, Rating.book_id == payload.book_id)
    )
    if rating is None:
        rating = Rating(**payload.model_dump())
        session.add(rating)
    else:
        rating.value = payload.value
    session.commit()
    session.refresh(rating)
    return rating
