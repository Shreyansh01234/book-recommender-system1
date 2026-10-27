from collections.abc import Sequence
from math import sqrt


def precision_at_k(ranked_ids: Sequence[str], relevant_ids: set[str], k: int) -> float:
    if k <= 0:
        raise ValueError("k must be greater than zero")
    return sum(book_id in relevant_ids for book_id in ranked_ids[:k]) / k


def recall_at_k(ranked_ids: Sequence[str], relevant_ids: set[str], k: int) -> float:
    if k <= 0:
        raise ValueError("k must be greater than zero")
    if not relevant_ids:
        return 0.0
    return sum(book_id in relevant_ids for book_id in ranked_ids[:k]) / len(relevant_ids)


def rmse(actual: Sequence[float], predicted: Sequence[float]) -> float:
    if len(actual) != len(predicted):
        raise ValueError("actual and predicted must have the same number of values")
    if not actual:
        raise ValueError("at least one rating is required")
    return sqrt(sum((truth - estimate) ** 2 for truth, estimate in zip(actual, predicted)) / len(actual))
