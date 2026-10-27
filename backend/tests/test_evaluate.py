import csv

import pytest

from scripts.evaluate import evaluate


def test_evaluate_uses_all_held_out_items_for_recall_and_rmse(tmp_path) -> None:
    path = tmp_path / "predictions.csv"
    rows = [
        {"user_id": "reader", "book_id": "relevant-hit", "rating": 5, "predicted_rating": 4, "rank": 1},
        {"user_id": "reader", "book_id": "relevant-miss", "rating": 4, "predicted_rating": 3, "rank": 0},
        {"user_id": "reader", "book_id": "not-relevant", "rating": 2, "predicted_rating": 2, "rank": 2},
    ]
    with path.open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    metrics = evaluate(path, k=2, relevance_threshold=4)

    assert metrics["precision@2"] == 0.5
    assert metrics["recall@2"] == 0.5
    assert metrics["rmse"] == pytest.approx((2 / 3) ** 0.5)
