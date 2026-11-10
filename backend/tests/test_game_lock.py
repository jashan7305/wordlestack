from typing import Any

from sqlalchemy.dialects.postgresql import dialect

from app.api.routes import lock_daily_game


class StatementCapture:
    statement: Any = None

    def scalar(self, statement: Any) -> None:
        self.statement = statement


def test_submission_lock_targets_only_the_game_row() -> None:
    session = StatementCapture()
    assert lock_daily_game(session, user_id=7, puzzle_id=12) is None
    sql = str(session.statement.compile(dialect=dialect()))
    assert "FOR UPDATE OF games" in sql
    assert "JOIN" not in sql
