import pytest

from app.services.game_engine import evaluate_guess, finish_evaluation, is_valid_guess


@pytest.mark.parametrize(
    ("answer", "guess", "expected"),
    [
        ("crane", "crane", "GGGGG"),
        ("crane", "sloth", "XXXXX"),
        ("apple", "alley", "GYXYX"),
        ("eerie", "erase", "GYXXG"),
        ("sassy", "assay", "YYGXG"),
    ],
)
def test_evaluation(answer: str, guess: str, expected: str) -> None:
    assert evaluate_guess(answer, guess) == expected


def test_game_completion_scoring() -> None:
    assert finish_evaluation("GGGGG", 1).points == 100
    assert finish_evaluation("GGGGG", 6).points == 10
    assert finish_evaluation("XXXXX", 6).completed
    assert finish_evaluation("XXXXX", 6).points == 0


def test_invalid_guess_shape_rejected_by_engine() -> None:
    with pytest.raises(ValueError):
        evaluate_guess("apple", "no")


def test_fixed_guess_dictionary() -> None:
    assert is_valid_guess("APPLE")
    assert is_valid_guess("zebra")
    assert not is_valid_guess("calm")
    assert not is_valid_guess("qzqzx")
    assert not is_valid_guess("café")
