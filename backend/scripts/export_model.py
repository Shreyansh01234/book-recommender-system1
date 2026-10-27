import hashlib
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = Path(__file__).resolve().parents[1] / "app" / "data"
GENRE_RULES = {
    "Fantasy": ("wizard", "magic", "dragon", "witch", "harry potter", "fantasy"),
    "Mystery": ("murder", "detective", "mystery", "crime", "killer"),
    "Romance": ("love", "romance", "bride", "wedding", "heart"),
    "Science Fiction": ("space", "robot", "galaxy", "sci-fi", "science fiction"),
    "History": ("history", "historical", "war", "biography", "memoir"),
    "Horror": ("horror", "vampire", "ghost", "haunted", "terror"),
    "Young Adult": ("teen", "school", "young adult", "adolescent"),
    "Nonfiction": ("guide", "cookbook", "encyclopedia", "philosophy", "psychology"),
}


def _text(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def _genres(title: str) -> list[str]:
    normalized = title.casefold()
    matches = [
        genre
        for genre, keywords in GENRE_RULES.items()
        if any(keyword in normalized for keyword in keywords)
    ]
    return matches or ["General"]


def _book_id(isbn: str, title: str, author: str) -> str:
    identity = f"{isbn.casefold()}|{title.casefold()}|{author.casefold()}"
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]


def export() -> tuple[int, int]:
    books = pd.read_pickle(ROOT / "books.pkl").fillna("")
    top = pd.read_pickle(ROOT / "top_50.pkl").fillna("")
    profile = pd.read_pickle(ROOT / "pt.pkl")
    similarities = np.asarray(pd.read_pickle(ROOT / "similarity.pkl"))

    popular_by_title = {
        _text(row["Book-Title"]).casefold(): row
        for _, row in top.iterrows()
        if _text(row["Book-Title"])
    }
    collaborative_titles = {_text(title).casefold() for title in profile.index}
    selected = books.loc[
        books["Book-Title"].map(lambda title: _text(title).casefold()).isin(collaborative_titles | popular_by_title.keys())
    ].drop_duplicates(subset=["Book-Title"], keep="first")

    catalog: list[dict[str, object]] = []
    book_id_by_title: dict[str, str] = {}
    for _, row in selected.iterrows():
        title = _text(row["Book-Title"])
        author = _text(row["Book-Author"]) or "Unknown author"
        popularity = popular_by_title.get(title.casefold(), {})
        isbn = _text(row["ISBN"])
        cover = _text(row["Image-URL-M"]).replace("http://", "https://", 1)
        book_id = _book_id(isbn, title, author)
        book_id_by_title[title.casefold()] = book_id
        catalog.append(
            {
                "id": book_id,
                "title": title,
                "author": author,
                "publisher": _text(row["Publisher"]),
                "published_year": int(row["Year-Of-Publication"])
                if str(row["Year-Of-Publication"]).isdigit()
                else None,
                "cover_url": cover,
                "genre_tags": _genres(title),
                "rating_count": int(popularity.get("no-rating", 0) or 0),
                "average_rating": float(popularity.get("avg-rating", 0) or 0) / 2,
            }
        )

    neighbors: dict[str, list[dict[str, str | float]]] = {}
    titles = [_text(title) for title in profile.index]
    for row_index, title in enumerate(titles):
        order = np.argsort(similarities[row_index])[::-1]
        neighbors[title] = [
            {"title": titles[column], "score": round(float(similarities[row_index, column]), 5)}
            for column in order
            if column != row_index and float(similarities[row_index, column]) > 0
            and titles[column].casefold() in book_id_by_title
        ][:30]

    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")
    (OUTPUT / "neighbors.json").write_text(json.dumps(neighbors, ensure_ascii=False), encoding="utf-8")
    return len(catalog), len(neighbors)


if __name__ == "__main__":
    catalog_count, model_count = export()
    print(f"Exported {catalog_count} catalog books and {model_count} collaborative-filtering profiles.")
