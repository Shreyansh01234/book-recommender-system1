import pytest

from app.metrics import precision_at_k, recall_at_k, rmse


def test_precision_at_k_counts_relevant_recommendations() -> None:
    assert precision_at_k(["a", "b", "c"], {"a", "c"}, 2) == 0.5


def test_recall_at_k_uses_all_relevant_items() -> None:
    assert recall_at_k(["a", "b", "c"], {"a", "c", "d"}, 2) == pytest.approx(1 / 3)


def test_rmse_calculates_rating_error() -> None:
    assert rmse([4, 2], [3, 2]) == pytest.approx(2**-0.5)


@pytest.mark.parametrize("k", [0, -1])
def test_ranking_metrics_reject_non_positive_k(k: int) -> None:
    with pytest.raises(ValueError, match="k must be greater than zero"):
        precision_at_k(["a"], {"a"}, k)


def test_rmse_rejects_mismatched_inputs() -> None:
    with pytest.raises(ValueError, match="same number"):
        rmse([4], [])
