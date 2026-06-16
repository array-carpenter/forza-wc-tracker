"""Fetch 2026 World Cup per-player stats from ESPN's free API.

ESPN exposes per-match rosters with full per-player stats (appearances,
goals, assists, yellow/red cards) for every player who features, not just
scorers. We aggregate those across every completed match. No API key.
"""

import datetime
import json
import time
from pathlib import Path

import requests

ESPN = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world"
# Fixed tournament window (June 11 - July 19, 2026). Scanning the whole window
# instead of "today" makes the fetch independent of the server's clock.
WC_DATES = "20260611-20260719"
CACHE_TTL_SECONDS = 8 * 3600  # refresh roughly 3x a day

# ESPN team-stat field -> label, for the per-match report.
REPORT_METRICS = [
    ("possessionPct", "Possession %"),
    ("totalShots", "Shots"),
    ("shotsOnTarget", "On target"),
    ("totalPasses", "Passes"),
    ("wonCorners", "Corners"),
    ("totalTackles", "Tackles"),
    ("foulsCommitted", "Fouls"),
]

# ESPN box-score field -> our column name. All are per-match counts we sum.
STAT_FIELDS = {
    "appearances": "Apps",
    "subIns": "Sub",
    "totalGoals": "Goals",
    "goalAssists": "Assists",
    "totalShots": "Shots",
    "shotsOnTarget": "SOG",
    "yellowCards": "Yellow",
    "redCards": "Red",
    "foulsCommitted": "Fouls",
    "foulsSuffered": "Fouled",
    "offsides": "Offsides",
    "ownGoals": "Own Goals",
    "saves": "Saves",
    "goalsConceded": "Conceded",
}

CACHE_DIR = Path(__file__).parent / "data"
CACHE_FILE = CACHE_DIR / "wc_players_cache.json"


def get_token() -> None:
    """ESPN needs no key; kept for API compatibility."""
    return None


def _completed_event_ids() -> set[str]:
    """Every completed World Cup match id across the whole tournament window."""
    ids: set[str] = set()
    try:
        resp = requests.get(f"{ESPN}/scoreboard", params={"dates": WC_DATES}, timeout=30)
        for e in resp.json().get("events", []):
            if e.get("status", {}).get("type", {}).get("completed"):
                ids.add(e["id"])
    except Exception:
        pass
    return ids


def _aggregate(event_ids: set[str]) -> list[dict]:
    """Sum each player's stats across the given matches."""
    agg: dict[str, dict] = {}
    for eid in event_ids:
        try:
            summary = requests.get(f"{ESPN}/summary", params={"event": eid}, timeout=20).json()
        except Exception:
            continue
        for team in summary.get("rosters", []) or []:
            nation = (team.get("team") or {}).get("displayName", "")
            for p in team.get("roster", []) or []:
                stats = p.get("stats")
                if not stats:
                    continue
                d = {s["name"]: s.get("value", 0) for s in stats}
                ath = p.get("athlete", {})
                key = str(ath.get("id") or ath.get("displayName", ""))
                rec = agg.setdefault(
                    key,
                    {"name": ath.get("displayName", ""), "nationality": nation,
                     **{col: 0 for col in STAT_FIELDS.values()}},
                )
                for field, col in STAT_FIELDS.items():
                    rec[col] += int(d.get(field, 0) or 0)
        time.sleep(0.15)
    return list(agg.values())


def _cache_is_fresh(cached: dict) -> bool:
    ts = cached.get("fetched_at")
    if not ts:
        return False
    try:
        age = (datetime.datetime.now() - datetime.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S"))
        return 0 <= age.total_seconds() < CACHE_TTL_SECONDS
    except Exception:
        return False


def load_player_stats(force_refresh: bool = False) -> dict:
    """Return WC player stats, refetching from ESPN when the cache is stale."""
    if CACHE_FILE.exists() and not force_refresh:
        cached = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        if _cache_is_fresh(cached):
            return cached
    try:
        players = _aggregate(_completed_event_ids())
        result = {
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "players": players,
            "source": "espn",
        }
        CACHE_DIR.mkdir(exist_ok=True)
        CACHE_FILE.write_text(json.dumps(result), encoding="utf-8")
        return result
    except Exception as exc:
        return {"fetched_at": None, "players": [], "source": "error", "error": str(exc)}


def clear_cache() -> None:
    CACHE_FILE.unlink(missing_ok=True)


def list_matches() -> list[dict]:
    """Completed matches with teams, scores, and crests, oldest first."""
    try:
        resp = requests.get(f"{ESPN}/scoreboard", params={"dates": WC_DATES}, timeout=30)
        out = []
        for e in resp.json().get("events", []):
            if not e.get("status", {}).get("type", {}).get("completed"):
                continue
            comp = (e.get("competitions") or [{}])[0]
            sides = {c.get("homeAway"): c for c in comp.get("competitors", [])}
            h, a = sides.get("home"), sides.get("away")
            if not h or not a:
                continue
            out.append({
                "id": e["id"], "date": (e.get("date") or "")[:10],
                "home": {"name": h["team"]["displayName"], "score": h.get("score"),
                         "logo": h["team"].get("logo")},
                "away": {"name": a["team"]["displayName"], "score": a.get("score"),
                         "logo": a["team"].get("logo")},
            })
        return sorted(out, key=lambda m: m["date"])
    except Exception:
        return []


def match_report(event_id: str) -> dict | None:
    """Both teams' box-score stats for one match."""
    try:
        summary = requests.get(f"{ESPN}/summary", params={"event": event_id}, timeout=30).json()
        teams = summary.get("boxscore", {}).get("teams", [])
        if len(teams) < 2:
            return None

        def pack(t):
            return {
                "name": t["team"].get("displayName"),
                "logo": t["team"].get("logo"),
                "stats": {x["name"]: x.get("displayValue") for x in t.get("statistics", [])},
            }

        by = {t.get("homeAway"): pack(t) for t in teams}
        return {"home": by.get("home"), "away": by.get("away")}
    except Exception:
        return None
