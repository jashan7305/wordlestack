from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.routes import update_stats
from app.db import Base
from app.models import Role, User, UserStats


def test_stats_initialize_and_update_after_game_completion() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(username="stat_player", password_hash="hashed", role=Role.USER)
        db.add(user)
        db.flush()

        update_stats(db, user.id, won=True, points=100)
        stats = db.get(UserStats, user.id)
        assert stats is not None
        assert (stats.played, stats.wins, stats.current_streak) == (1, 1, 1)
        assert (stats.longest_streak, stats.total_points) == (1, 100)

        update_stats(db, user.id, won=False, points=0)
        assert (stats.played, stats.wins, stats.current_streak) == (2, 1, 0)
        assert stats.total_points == 100
        db.commit()
    engine.dispose()
