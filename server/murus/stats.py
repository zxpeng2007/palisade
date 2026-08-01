"""Site statistics: what a daily check wants to know.

Public, because everything else here is. The numbers are aggregates over data
already visible one page at a time -- who is registered, what they played --
so publishing the totals reveals nothing the site does not already show, and
a site that asks people to trust its ratings should be willing to say how
many games those ratings rest on.

Deliberately answers "what changed" and not only "what exists". A total is
almost useless on its own: 7 accounts is the same number whether six of them
arrived this morning or nobody has visited in a month.
"""

from __future__ import annotations

from murus import db, speed
from murus.events import online_ids


def _scalar(sql: str, args: tuple = ()) -> int:
    row = db.one(sql, args)
    return int(row[0]) if row and row[0] is not None else 0


def _window(table: str, column: str, hours: int) -> int:
    return _scalar(
        f"SELECT count(*) FROM {table} "
        f"WHERE {column} >= datetime('now', ?)", (f"-{hours} hours",))


def collect() -> dict:
    """One snapshot of the site. Cheap: a handful of counts over small tables."""
    from murus.games import manager

    users_total = _scalar("SELECT count(*) FROM users")
    bots = _scalar("SELECT count(*) FROM users WHERE is_bot = 1")
    finished = "status = 'finished'"

    by_speed: dict[str, int] = {}
    for row in db.query(
        f"SELECT initial, increment, count(*) AS n FROM games "
        f"WHERE {finished} GROUP BY initial, increment"
    ):
        cat = speed.category(row["initial"], row["increment"])
        by_speed[cat] = by_speed.get(cat, 0) + int(row["n"])

    by_reason = {
        r["reason"]: int(r["n"])
        for r in db.query(
            f"SELECT reason, count(*) AS n FROM games WHERE {finished} "
            f"AND reason IS NOT NULL GROUP BY reason")
    }

    # Engine games are counted "at least one engine", matching how the top
    # games endpoint splits them, so the two numbers can be compared.
    engine_games = _scalar(
        f"SELECT count(*) FROM games g JOIN users a ON a.id = g.p1 "
        f"JOIN users b ON b.id = g.p2 WHERE {finished} "
        f"AND (a.is_bot = 1 OR b.is_bot = 1)")

    reviews = {
        r["status"]: int(r["n"])
        for r in db.query("SELECT status, count(*) AS n FROM reviews "
                          "GROUP BY status")
    }

    longest = db.one(
        f"SELECT id, length(moves) - length(replace(moves, ',', '')) + 1 AS plies "
        f"FROM games WHERE {finished} AND moves != '' "
        f"ORDER BY plies DESC LIMIT 1")

    # Who is actually connected right now. The only way to tell from outside
    # whether the house bot is alive: a site with no games might be quiet, or
    # might have a dead engine, and those need different responses.
    online = online_ids()
    engines_online = []
    if online:
        marks = ",".join("?" * len(online))
        engines_online = [
            r["username"] for r in db.query(
                f"SELECT username FROM users WHERE is_bot = 1 AND id IN ({marks})",
                tuple(online))
        ]

    return {
        "online": {"total": len(online), "engines": sorted(engines_online)},
        "users": {
            "total": users_total,
            "human": users_total - bots,
            "bot": bots,
            "verified": _scalar("SELECT count(*) FROM users WHERE email_verified = 1"),
            "titled": _scalar("SELECT count(*) FROM users WHERE title IS NOT NULL"),
            "withRatedGames": _scalar("SELECT count(*) FROM users WHERE rated_games > 0"),
            "new24h": _window("users", "created", 24),
            "new7d": _window("users", "created", 24 * 7),
        },
        "games": {
            "total": _scalar(f"SELECT count(*) FROM games WHERE {finished}"),
            "rated": _scalar(f"SELECT count(*) FROM games WHERE {finished} AND rated = 1"),
            "withEngine": engine_games,
            "aborted": _scalar("SELECT count(*) FROM games WHERE status = 'aborted'"),
            "live": len(manager.live),
            "finished24h": _window("games", "finished", 24),
            "finished7d": _window("games", "finished", 24 * 7),
            "bySpeed": by_speed,
            "byReason": by_reason,
            "longest": ({"id": longest["id"], "plies": int(longest["plies"])}
                        if longest else None),
        },
        "reviews": {
            "done": reviews.get("done", 0),
            "running": reviews.get("running", 0) + reviews.get("pending", 0),
            "failed": reviews.get("failed", 0),
        },
        "ladder": [
            {"username": r["username"], "rating": round(r["rating"]),
             "bot": bool(r["is_bot"]), "title": r["title"],
             "games": r["rated_games"],
             "provisional": r["rd"] > 110}
            for r in db.query(
                "SELECT username, rating, is_bot, title, rated_games, rd "
                "FROM users WHERE rated_games > 0 "
                "ORDER BY rd > 110, rating DESC LIMIT 5")
        ],
    }
