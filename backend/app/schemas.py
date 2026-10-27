from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BookOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    author: str
    publisher: str
    published_year: int | None
    cover_url: str
    genre_tags: list[str]
    rating_count: int
    average_rating: float


class UserCreate(BaseModel):
    id: str = Field(min_length=1, max_length=36)
    display_name: str = Field(default="Reader", min_length=1, max_length=80)
    preferred_genres: list[str] = Field(default_factory=list, max_length=12)
    preferred_authors: list[str] = Field(default_factory=list, max_length=12)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    display_name: str
    preferred_genres: list[str]
    preferred_authors: list[str]
    created_at: datetime


class PreferencesUpdate(BaseModel):
    preferred_genres: list[str] = Field(default_factory=list, max_length=12)
    preferred_authors: list[str] = Field(default_factory=list, max_length=12)


class RatingCreate(BaseModel):
    user_id: str = Field(min_length=1, max_length=36)
    book_id: str = Field(min_length=1, max_length=40)
    value: float = Field(ge=1, le=5)


class RatingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: str
    book_id: str
    value: float
    created_at: datetime


class RecommendationOut(BaseModel):
    book: BookOut
    score: float
    reasons: list[str]
    model_mix: str
