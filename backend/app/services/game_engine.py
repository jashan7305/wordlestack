from dataclasses import dataclass
from pathlib import Path

MAX_ATTEMPTS = 6
POINTS_BY_GUESSES = {1: 100, 2: 80, 3: 60, 4: 40, 5: 20, 6: 10}


@dataclass(frozen=True)
class Evaluation:
    pattern: str
    won: bool
    completed: bool
    points: int


def evaluate_guess(answer: str, guess: str) -> str:
    """Return G/Y/X feedback while accounting for repeated letters."""
    answer, guess = answer.lower(), guess.lower()
    if (
        len(answer) != 5
        or len(guess) != 5
        or not answer.isalpha()
        or not guess.isalpha()
    ):
        raise ValueError("Answer and guess must be five-letter words")
    result = ["X"] * 5
    remaining: dict[str, int] = {}
    for index, (actual, submitted) in enumerate(zip(answer, guess, strict=True)):
        if actual == submitted:
            result[index] = "G"
        else:
            remaining[actual] = remaining.get(actual, 0) + 1
    for index, submitted in enumerate(guess):
        if result[index] == "G":
            continue
        if remaining.get(submitted, 0):
            result[index] = "Y"
            remaining[submitted] -= 1
    return "".join(result)


def finish_evaluation(pattern: str, attempt: int) -> Evaluation:
    won = pattern == "GGGGG"
    completed = won or attempt >= MAX_ATTEMPTS
    return Evaluation(
        pattern, won, completed, POINTS_BY_GUESSES.get(attempt, 0) if won else 0
    )


def is_valid_guess(word: str) -> bool:
    return (
        len(word) == 5
        and word.isascii()
        and word.isalpha()
        and word.lower() in VALID_GUESSES
    )


_WORD_LIST = Path(__file__).resolve().parents[1] / "data" / "guess_words.txt"
VALID_GUESSES = frozenset(_WORD_LIST.read_text(encoding="utf-8").splitlines())
