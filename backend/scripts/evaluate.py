import argparse
import csv
from collections import defaultdict
from pathlib import Path

from app.metrics import precision_at_k, recall_at_k, rmse


def evaluate(path: Path, k: int, relevance_threshold: float) -> dict[str, float]:
    ranked: dict[str, list[tuple[int, str]]] = defaultdict(list)
    relevant: dict[str, set[str]] = defaultdict(set)
    actual: list[float] = []
    predicted: list[float] = []
    with path.open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        required = {"user_id", "book_id", "rating", "predicted_rating", "rank"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(f"CSV must include these columns: {', '.join(sorted(required))}")
        for row in reader:
            user_id = row["user_id"]
            book_id = row["book_id"]
            rating = float(row["rating"])
            actual.append(rating)
            predicted.append(float(row["predicted_rating"]))
            rank = int(row["rank"] or 0)
            if rank > 0:
                ranked[user_id].append((rank, book_id))
            if rating >= relevance_threshold:
                relevant[user_id].add(book_id)

    if not actual:
        raise ValueError("CSV contains no evaluation rows")
    precisions = []
    recalls = []
    for user_id, entries in ranked.items():
        ordered_ids = [book_id for _, book_id in sorted(entries)][:k]
        precisions.append(precision_at_k(ordered_ids, relevant[user_id], k))
        recalls.append(recall_at_k(ordered_ids, relevant[user_id], k))
    return {
        f"precision@{k}": sum(precisions) / len(precisions),
        f"recall@{k}": sum(recalls) / len(recalls),
        "rmse": rmse(actual, predicted),
        "users": float(len(ranked)),
        "ratings": float(len(actual)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate held-out hybrid recommendation predictions.")
    parser.add_argument("ratings_csv", type=Path)
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--relevance-threshold", type=float, default=4.0)
    args = parser.parse_args()
    if args.k <= 0:
        parser.error("--k must be greater than zero")
    for metric, value in evaluate(args.ratings_csv, args.k, args.relevance_threshold).items():
        print(f"{metric}: {value:.4f}")


if __name__ == "__main__":
    main()
