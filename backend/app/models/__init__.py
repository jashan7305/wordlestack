from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Role(StrEnum):
    USER = "USER"
    ADMIN = "ADMIN"


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.USER)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    games: Mapped[list[Game]] = relationship(back_populates="user")


class Puzzle(Base):
    __tablename__ = "puzzles"
    id: Mapped[int] = mapped_column(primary_key=True)
    print_date: Mapped[date] = mapped_column(Date, unique=True, index=True)
    solution: Mapped[str] = mapped_column(String(5))
    days_since_launch: Mapped[int | None] = mapped_column(Integer, nullable=True)
    editor: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    games: Mapped[list[Game]] = relationship(back_populates="puzzle")


class Game(Base):
    __tablename__ = "games"
    __table_args__ = (
        UniqueConstraint("user_id", "puzzle_id", name="uq_game_user_puzzle"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    puzzle_id: Mapped[int] = mapped_column(
        ForeignKey("puzzles.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[str] = mapped_column(String(12), default="playing")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    points: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    user: Mapped[User] = relationship(back_populates="games")
    puzzle: Mapped[Puzzle] = relationship(back_populates="games")
    guesses: Mapped[list[Guess]] = relationship(
        back_populates="game", cascade="all, delete-orphan", order_by="Guess.position"
    )


class Guess(Base):
    __tablename__ = "guesses"
    __table_args__ = (
        UniqueConstraint("game_id", "position", name="uq_guess_position"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    word: Mapped[str] = mapped_column(String(5))
    result: Mapped[str] = mapped_column(String(5))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    game: Mapped[Game] = relationship(back_populates="guesses")


class UserStats(Base):
    __tablename__ = "user_stats"
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    played: Mapped[int] = mapped_column(Integer, default=0)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    current_streak: Mapped[int] = mapped_column(Integer, default=0)
    longest_streak: Mapped[int] = mapped_column(Integer, default=0)
    total_points: Mapped[int] = mapped_column(Integer, default=0)


class League(Base):
    __tablename__ = "leagues"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    members: Mapped[list[LeagueMember]] = relationship(
        back_populates="league", cascade="all, delete-orphan"
    )


class LeagueMember(Base):
    __tablename__ = "league_members"
    __table_args__ = (
        UniqueConstraint("league_id", "user_id", name="uq_league_member"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(
        ForeignKey("leagues.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    league: Mapped[League] = relationship(back_populates="members")
    user: Mapped[User] = relationship()


class LeagueInvite(Base):
    __tablename__ = "league_invites"
    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(
        ForeignKey("leagues.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
