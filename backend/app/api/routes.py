from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.api.deps import admin_user, csrf_check, current_user
from app.core.config import settings
from app.core.security import (
    hash_password,
    issue_token,
    new_invitation_token,
    token_hash,
    verify_password,
)
from app.db import get_db
from app.models import (
    Game,
    Guess,
    League,
    LeagueInvite,
    LeagueMember,
    Puzzle,
    Role,
    User,
    UserStats,
)
from app.services.game_engine import evaluate_guess, finish_evaluation, is_valid_guess
from app.services.wordle_provider import ProviderError, sync_puzzle

router = APIRouter(prefix="/api/v1")


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_]+$")
    password: str = Field(min_length=10, max_length=128)


class GuessInput(BaseModel):
    guess: str = Field(min_length=5, max_length=5, pattern=r"^[A-Za-z]{5}$")


class LeagueInput(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    description: str = Field(default="", max_length=500)
    archived: bool | None = None


class MemberInput(BaseModel):
    user_id: int


class AdminUserPatch(BaseModel):
    active: bool | None = None
    role: Role | None = None


def today_local() -> date:
    return datetime.now(ZoneInfo(settings.TIMEZONE)).date()


def safe_game(game: Game, reveal: bool = False) -> dict[str, object]:
    return {
        "id": game.id,
        "date": game.puzzle.print_date,
        "status": game.status,
        "attempts": game.attempts,
        "points": game.points,
        "guesses": [{"word": row.word, "result": row.result} for row in game.guesses],
        "answer": game.puzzle.solution if reveal else None,
    }


def obtain_game(db: Session, user: User, puzzle: Puzzle) -> Game:
    game = db.scalar(
        select(Game)
        .options(joinedload(Game.guesses), joinedload(Game.puzzle))
        .where(Game.user_id == user.id, Game.puzzle_id == puzzle.id)
    )
    if game:
        return game
    game = Game(user_id=user.id, puzzle_id=puzzle.id)
    db.add(game)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        game = db.scalar(
            select(Game)
            .options(joinedload(Game.guesses), joinedload(Game.puzzle))
            .where(Game.user_id == user.id, Game.puzzle_id == puzzle.id)
        )
        if game is None:
            raise
        return game
    db.refresh(game)
    return game


def lock_daily_game(db: Session, user_id: int, puzzle_id: int) -> Game | None:
    """Lock only the game row; locking eager-loaded outer joins fails on PostgreSQL."""
    return db.scalar(
        select(Game)
        .where(Game.user_id == user_id, Game.puzzle_id == puzzle_id)
        .with_for_update(of=Game)
    )


async def puzzle_for(db: Session, puzzle_date: date) -> Puzzle:
    try:
        return await sync_puzzle(db, puzzle_date)
    except ProviderError as exc:
        raise HTTPException(
            status_code=503,
            detail="Puzzle is not cached and the official provider is unavailable",
        ) from exc


def invitation_for_token(db: Session, token: str) -> LeagueInvite:
    invite = db.scalar(
        select(LeagueInvite)
        .where(LeagueInvite.token_hash == token_hash(token))
        .with_for_update()
    )
    if not invite or invite.revoked or invite.expires_at < datetime.now(UTC):
        raise HTTPException(404, "Invitation is invalid or expired")
    return invite


@router.post("/auth/register", status_code=201)
def register(
    data: Credentials,
    response: Response,
    invite: str | None = None,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    username = data.username.lower()
    if db.scalar(select(User).where(func.lower(User.username) == username)):
        raise HTTPException(409, "Username is already in use")
    invitation = invitation_for_token(db, invite) if invite else None
    user = User(
        username=username, password_hash=hash_password(data.password), role=Role.USER
    )
    db.add(user)
    try:
        db.flush()
        if invitation:
            db.add(LeagueMember(league_id=invitation.league_id, user_id=user.id))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Username is already in use") from exc
    db.refresh(user)
    set_auth_cookies(response, user.id)
    return {"id": user.id, "username": user.username, "role": user.role.value}


def set_auth_cookies(response: Response, user_id: int) -> None:
    from secrets import token_urlsafe

    csrf = token_urlsafe(24)
    response.set_cookie(
        "wordlestack_session",
        issue_token(user_id),
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=1209600,
        path="/",
    )
    response.set_cookie(
        "csrf_cookie",
        csrf,
        httponly=False,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=1209600,
        path="/",
    )


@router.post("/auth/login")
def login(
    data: Credentials,
    response: Response,
    invite: str | None = None,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    user = db.scalar(
        select(User).where(func.lower(User.username) == data.username.lower())
    )
    if (
        not user
        or not verify_password(data.password, user.password_hash)
        or not user.active
    ):
        raise HTTPException(401, "Username or password is incorrect")
    if invite:
        invitation = invitation_for_token(db, invite)
        existing = db.scalar(
            select(LeagueMember.id).where(
                LeagueMember.league_id == invitation.league_id,
                LeagueMember.user_id == user.id,
            )
        )
        if not existing:
            db.add(LeagueMember(league_id=invitation.league_id, user_id=user.id))
            db.commit()
    set_auth_cookies(response, user.id)
    return {"id": user.id, "username": user.username, "role": user.role.value}


@router.post("/auth/logout", dependencies=[Depends(csrf_check)])
def logout(response: Response) -> dict[str, str]:
    response.delete_cookie("wordlestack_session", path="/")
    response.delete_cookie("csrf_cookie", path="/")
    return {"status": "signed out"}


@router.get("/auth/me")
def me(user: User = Depends(current_user)) -> dict[str, object]:
    return {"id": user.id, "username": user.username, "role": user.role.value}


@router.get("/puzzles/today")
async def puzzle_today(db: Session = Depends(get_db)) -> dict[str, object]:
    puzzle = await puzzle_for(db, today_local())
    return {
        "date": puzzle.print_date,
        "days_since_launch": puzzle.days_since_launch,
        "editor": puzzle.editor,
    }


@router.get("/puzzles/{puzzle_date}")
async def puzzle_by_date(
    puzzle_date: date, db: Session = Depends(get_db)
) -> dict[str, object]:
    if puzzle_date > today_local():
        raise HTTPException(404, "Puzzle not found")
    puzzle = await puzzle_for(db, puzzle_date)
    return {
        "date": puzzle.print_date,
        "days_since_launch": puzzle.days_since_launch,
        "editor": puzzle.editor,
    }


@router.get("/games/today")
async def game_today(
    db: Session = Depends(get_db), user: User = Depends(current_user)
) -> dict[str, object]:
    puzzle = await puzzle_for(db, today_local())
    game = obtain_game(db, user, puzzle)
    return safe_game(game, game.status != "playing")


@router.post("/games/today/guess", dependencies=[Depends(csrf_check)])
async def submit_guess(
    data: GuessInput, db: Session = Depends(get_db), user: User = Depends(current_user)
) -> dict[str, object]:
    word = data.guess.lower()
    if not is_valid_guess(word):
        raise HTTPException(422, "That word is not in the five-letter guess list")
    puzzle = await puzzle_for(db, today_local())
    game = lock_daily_game(db, user.id, puzzle.id)
    if not game:
        obtain_game(db, user, puzzle)
        game = lock_daily_game(db, user.id, puzzle.id)
    if not game:
        raise HTTPException(500, "Unable to load the daily game")
    if game.status != "playing":
        raise HTTPException(409, "This game is already complete")
    pattern = evaluate_guess(puzzle.solution, word)
    attempt = game.attempts + 1
    result = finish_evaluation(pattern, attempt)
    game.attempts = attempt
    game.status = "won" if result.won else "lost" if result.completed else "playing"
    game.points = result.points
    if result.completed:
        game.completed_at = datetime.now(UTC)
    game.guesses.append(Guess(position=attempt, word=word, result=pattern))
    if result.completed:
        update_stats(db, user.id, result.won, result.points)
    db.commit()
    db.refresh(game)
    return safe_game(game, result.completed)


def update_stats(db: Session, user_id: int, won: bool, points: int) -> None:
    stats = db.get(UserStats, user_id)
    if not stats:
        stats = UserStats(
            user_id=user_id,
            played=0,
            wins=0,
            current_streak=0,
            longest_streak=0,
            total_points=0,
        )
        db.add(stats)
    stats.played = (stats.played or 0) + 1
    stats.total_points = (stats.total_points or 0) + points
    if won:
        stats.wins = (stats.wins or 0) + 1
        stats.current_streak = (stats.current_streak or 0) + 1
        stats.longest_streak = max(stats.longest_streak or 0, stats.current_streak)
    else:
        stats.current_streak = 0


@router.get("/games/history")
def history(
    page: int = Query(1, ge=1),
    limit: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, object]:
    rows = (
        db.scalars(
            select(Game)
            .options(joinedload(Game.puzzle), joinedload(Game.guesses))
            .where(Game.user_id == user.id)
            .order_by(Game.puzzle_id.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        .unique()
        .all()
    )
    return {
        "items": [safe_game(row, True) for row in rows],
        "page": page,
        "limit": limit,
    }


@router.get("/games/{game_id}")
def get_game(
    game_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)
) -> dict[str, object]:
    game = db.scalar(
        select(Game)
        .options(joinedload(Game.puzzle), joinedload(Game.guesses))
        .where(Game.id == game_id)
    )
    if not game or game.user_id != user.id:
        raise HTTPException(404, "Game not found")
    return safe_game(game, game.status != "playing")


@router.get("/leagues")
def leagues(
    db: Session = Depends(get_db), user: User = Depends(current_user)
) -> list[dict[str, object]]:
    rows = db.scalars(
        select(League)
        .join(LeagueMember)
        .where(LeagueMember.user_id == user.id)
        .order_by(League.name)
    ).all()
    return [
        {
            "id": row.id,
            "name": row.name,
            "description": row.description,
            "archived": row.archived,
        }
        for row in rows
    ]


def require_member(db: Session, league_id: int, user_id: int) -> League:
    league = db.get(League, league_id)
    user = db.get(User, user_id)
    member = db.scalar(
        select(LeagueMember.id).where(
            LeagueMember.league_id == league_id, LeagueMember.user_id == user_id
        )
    )
    if not league or (not member and (not user or user.role != Role.ADMIN)):
        raise HTTPException(404, "League not found")
    return league


@router.get("/leagues/{league_id}")
def league_detail(
    league_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)
) -> dict[str, object]:
    league = require_member(db, league_id, user.id)
    return {
        "id": league.id,
        "name": league.name,
        "description": league.description,
        "archived": league.archived,
    }


@router.get("/leagues/{league_id}/members")
def league_members(
    league_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)
) -> list[dict[str, object]]:
    require_member(db, league_id, user.id)
    rows = db.scalars(
        select(LeagueMember)
        .options(joinedload(LeagueMember.user))
        .where(LeagueMember.league_id == league_id)
    ).all()
    return [{"id": row.user.id, "username": row.user.username} for row in rows]


@router.get("/leagues/{league_id}/leaderboard/daily")
def daily_leaderboard(
    league_id: int,
    puzzle_date: date | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, object]:
    require_member(db, league_id, user.id)
    day = puzzle_date or today_local()
    members = db.scalars(
        select(LeagueMember)
        .options(joinedload(LeagueMember.user))
        .where(LeagueMember.league_id == league_id)
    ).all()
    puzzle = db.scalar(select(Puzzle).where(Puzzle.print_date == day))
    results = []
    for member in members:
        game = (
            db.scalar(
                select(Game).where(
                    Game.user_id == member.user_id, Game.puzzle_id == puzzle.id
                )
            )
            if puzzle
            else None
        )
        results.append(
            {
                "username": member.user.username,
                "status": game.status if game else "not_played",
                "guesses": game.attempts if game else None,
                "completion_time": (game.completed_at - game.started_at).total_seconds()
                if game and game.completed_at
                else None,
            }
        )
    results.sort(
        key=lambda row: (
            row["status"] == "not_played",
            row["status"] != "won",
            row["guesses"] or 99,
            row["completion_time"] or 10**9,
            row["username"],
        )
    )
    played = [
        dict(position=i + 1, **row)
        for i, row in enumerate(x for x in results if x["status"] != "not_played")
    ]
    return {
        "played": played,
        "not_played": [x for x in results if x["status"] == "not_played"],
    }


@router.get("/leagues/{league_id}/leaderboard/overall")
def league_overall(
    league_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)
) -> list[dict[str, object]]:
    require_member(db, league_id, user.id)
    members = db.scalars(
        select(LeagueMember)
        .options(joinedload(LeagueMember.user))
        .where(LeagueMember.league_id == league_id)
    ).all()
    rows = []
    for member in members:
        games = db.scalars(
            select(Game)
            .options(joinedload(Game.puzzle))
            .join(Puzzle)
            .where(Game.user_id == member.user_id, Game.status != "playing")
            .order_by(Puzzle.print_date)
        ).all()
        wins = sum(game.status == "won" for game in games)
        streak = longest_streak = 0
        previous_date = None
        for game in games:
            game_date = game.puzzle.print_date
            if game.status == "won":
                streak = (
                    streak + 1
                    if previous_date and game_date == previous_date + timedelta(days=1)
                    else 1
                )
                longest_streak = max(longest_streak, streak)
            else:
                streak = 0
            previous_date = game_date
        if previous_date is None or previous_date < today_local() - timedelta(days=1):
            streak = 0
        rows.append(
            {
                "username": member.user.username,
                "games_played": len(games),
                "wins": wins,
                "win_percentage": round(wins * 100 / len(games), 1) if games else 0,
                "average_guesses": round(
                    sum(game.attempts for game in games) / len(games), 2
                )
                if games
                else None,
                "current_streak": streak,
                "longest_streak": longest_streak,
                "total_points": sum(g.points for g in games),
            }
        )
    rows.sort(key=lambda x: (-x["total_points"], -x["wins"], x["username"]))
    return [dict(rank=index + 1, **row) for index, row in enumerate(rows)]


@router.get("/invitations/{token}")
def invitation_info(token: str, db: Session = Depends(get_db)) -> dict[str, object]:
    invite = db.scalar(
        select(LeagueInvite).where(LeagueInvite.token_hash == token_hash(token))
    )
    if not invite or invite.revoked or invite.expires_at < datetime.now(UTC):
        raise HTTPException(404, "Invitation is invalid or expired")
    league = db.get(League, invite.league_id)
    return {"league": {"id": league.id, "name": league.name}}


@router.post("/invitations/{token}/accept", dependencies=[Depends(csrf_check)])
def accept_invitation(
    token: str, db: Session = Depends(get_db), user: User = Depends(current_user)
) -> dict[str, str]:
    invite = db.scalar(
        select(LeagueInvite)
        .where(LeagueInvite.token_hash == token_hash(token))
        .with_for_update()
    )
    if not invite or invite.revoked or invite.expires_at < datetime.now(UTC):
        raise HTTPException(404, "Invitation is invalid or expired")
    if not db.scalar(
        select(LeagueMember.id).where(
            LeagueMember.league_id == invite.league_id, LeagueMember.user_id == user.id
        )
    ):
        db.add(LeagueMember(league_id=invite.league_id, user_id=user.id))
        db.commit()
    return {"status": "joined"}


@router.get("/stats/me")
def my_stats(
    db: Session = Depends(get_db), user: User = Depends(current_user)
) -> dict[str, object]:
    games = db.scalars(
        select(Game)
        .options(joinedload(Game.puzzle))
        .where(Game.user_id == user.id, Game.status != "playing")
        .join(Puzzle)
        .order_by(Puzzle.print_date)
    ).all()
    wins = [game for game in games if game.status == "won"]
    streak = longest = 0
    previous_date = None
    for game in games:
        day = game.puzzle.print_date
        if game.status == "won":
            streak = (
                streak + 1
                if previous_date and day == previous_date + timedelta(days=1)
                else 1
            )
            longest = max(longest, streak)
        else:
            streak = 0
        previous_date = day
    if previous_date is None or previous_date < today_local() - timedelta(days=1):
        streak = 0
    return {
        "games_played": len(games),
        "games_won": len(wins),
        "win_percentage": round(100 * len(wins) / len(games), 1) if games else 0,
        "current_streak": streak,
        "longest_streak": longest,
        "average_guesses": round(sum(g.attempts for g in games) / len(games), 2)
        if games
        else None,
        "total_points": sum(g.points for g in games),
        "guess_distribution": {
            str(n): sum(g.status == "won" and g.attempts == n for g in games)
            for n in range(1, 7)
        },
    }


@router.get("/leaderboard/global")
def global_leaderboard(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[dict[str, object]]:
    ids = db.scalars(select(User.id).where(User.active.is_(True))).all()
    rows = []
    for user_id in ids:
        stats = my_stats(db, db.get(User, user_id))
        person = db.get(User, user_id)
        rows.append({"username": person.username, **stats})
    rows.sort(
        key=lambda row: (-row["total_points"], -row["games_won"], row["username"])
    )
    return [
        dict(rank=index + 1, **row)
        for index, row in enumerate(rows[(page - 1) * limit : page * limit])
    ]


@router.get("/admin/users")
def admin_users(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: User = Depends(admin_user),
) -> dict[str, object]:
    rows = db.scalars(
        select(User).order_by(User.id).offset((page - 1) * limit).limit(limit)
    ).all()
    return {
        "items": [
            {
                "id": x.id,
                "username": x.username,
                "role": x.role.value,
                "active": x.active,
            }
            for x in rows
        ],
        "page": page,
    }


@router.patch("/admin/users/{user_id}", dependencies=[Depends(csrf_check)])
def patch_user(
    user_id: int,
    data: AdminUserPatch,
    db: Session = Depends(get_db),
    admin: User = Depends(admin_user),
) -> dict[str, object]:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    if (
        (data.active is False or data.role == Role.USER)
        and user.active
        and user.role == Role.ADMIN
    ):
        admin_count = (
            db.scalar(
                select(func.count(User.id)).where(
                    User.active.is_(True), User.role == Role.ADMIN
                )
            )
            or 0
        )
        if admin_count <= 1:
            raise HTTPException(
                409, "The last active administrator cannot be removed or demoted"
            )
    if data.active is not None:
        user.active = data.active
    if data.role is not None:
        user.role = data.role
    db.commit()
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role.value,
        "active": user.active,
    }


@router.post("/admin/leagues", status_code=201, dependencies=[Depends(csrf_check)])
def create_league(
    data: LeagueInput, db: Session = Depends(get_db), admin: User = Depends(admin_user)
) -> dict[str, object]:
    league = League(name=data.name.strip(), description=data.description.strip())
    db.add(league)
    db.commit()
    db.refresh(league)
    return {"id": league.id, "name": league.name, "description": league.description}


@router.patch("/admin/leagues/{league_id}", dependencies=[Depends(csrf_check)])
def edit_league(
    league_id: int,
    data: LeagueInput,
    db: Session = Depends(get_db),
    admin: User = Depends(admin_user),
) -> dict[str, object]:
    league = db.get(League, league_id)
    if not league:
        raise HTTPException(404, "League not found")
    league.name, league.description = data.name.strip(), data.description.strip()
    if data.archived is not None:
        league.archived = data.archived
    db.commit()
    return {"id": league.id, "name": league.name, "description": league.description}


@router.post(
    "/admin/leagues/{league_id}/members",
    status_code=201,
    dependencies=[Depends(csrf_check)],
)
def add_member(
    league_id: int,
    data: MemberInput,
    db: Session = Depends(get_db),
    admin: User = Depends(admin_user),
) -> dict[str, str]:
    league = db.get(League, league_id)
    if not league or not db.get(User, data.user_id):
        raise HTTPException(404, "League or user not found")
    if league.archived:
        raise HTTPException(409, "Archived Leagues cannot accept members")
    if db.scalar(
        select(LeagueMember.id).where(
            LeagueMember.league_id == league_id, LeagueMember.user_id == data.user_id
        )
    ):
        raise HTTPException(409, "User is already a member")
    db.add(LeagueMember(league_id=league_id, user_id=data.user_id))
    db.commit()
    return {"status": "added"}


@router.delete(
    "/admin/leagues/{league_id}/members/{user_id}", dependencies=[Depends(csrf_check)]
)
def remove_member(
    league_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(admin_user),
) -> dict[str, str]:
    membership = db.scalar(
        select(LeagueMember).where(
            LeagueMember.league_id == league_id, LeagueMember.user_id == user_id
        )
    )
    if not membership:
        raise HTTPException(404, "Membership not found")
    db.delete(membership)
    db.commit()
    return {"status": "removed"}


@router.post(
    "/admin/leagues/{league_id}/invitations",
    status_code=201,
    dependencies=[Depends(csrf_check)],
)
def create_invitation(
    league_id: int, db: Session = Depends(get_db), admin: User = Depends(admin_user)
) -> dict[str, object]:
    league = db.get(League, league_id)
    if not league:
        raise HTTPException(404, "League not found")
    if league.archived:
        raise HTTPException(409, "Archived Leagues cannot create invitations")
    token = new_invitation_token()
    expires = datetime.now(UTC) + timedelta(days=7)
    db.add(
        LeagueInvite(
            league_id=league_id, token_hash=token_hash(token), expires_at=expires
        )
    )
    db.commit()
    return {
        "url": f"{settings.PUBLIC_URL.rstrip('/')}/join/{token}",
        "expires_at": expires,
    }


@router.get("/admin/leagues")
def admin_leagues(
    db: Session = Depends(get_db), admin: User = Depends(admin_user)
) -> list[dict[str, object]]:
    rows = db.scalars(select(League).order_by(League.name)).all()
    return [
        {
            "id": row.id,
            "name": row.name,
            "description": row.description,
            "archived": row.archived,
        }
        for row in rows
    ]


@router.delete(
    "/admin/leagues/{league_id}/invitations/{invite_id}",
    dependencies=[Depends(csrf_check)],
)
def revoke_invitation(
    league_id: int,
    invite_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(admin_user),
) -> dict[str, str]:
    invite = db.scalar(
        select(LeagueInvite).where(
            LeagueInvite.id == invite_id, LeagueInvite.league_id == league_id
        )
    )
    if not invite:
        raise HTTPException(404, "Invitation not found")
    invite.revoked = True
    db.commit()
    return {"status": "revoked"}
