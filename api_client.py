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
WC_START = datetime.date(2026, 6, 11)

CACHE_DIR = Path(__file__).parent / "data"
CACHE_FILE = CACHE_DIR / "wc_players_cache.json"


def get_token() -> None:
    """ESPN needs no key; kept for API compatibility."""
    return None


def _completed_event_ids() -> set[str]:
    """Every completed World Cup match id from kickoff through today."""
    ids: set[str] = set()
    day, today = WC_START, datetime.date.today()
    while day <= today:
        try:
            resp = requests.get(
                f"{ESPN}/scoreboard", params={"dates": day.strftime("%Y%m%d")}, timeout=20
            )
            for e in resp.json().get("events", []):
                if e.get("status", {}).get("type", {}).get("completed"):
                    ids.add(e["id"])
        except Exception:
            pass
        day += datetime.timedelta(days=1)
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
                     "Apps": 0, "Goals": 0, "Assists": 0, "Yellow": 0, "Red": 0},
                )
                rec["Apps"] += int(d.get("appearances", 0) or 0)
                rec["Goals"] += int(d.get("totalGoals", 0) or 0)
                rec["Assists"] += int(d.get("goalAssists", 0) or 0)
                rec["Yellow"] += int(d.get("yellowCards", 0) or 0)
                rec["Red"] += int(d.get("redCards", 0) or 0)
        time.sleep(0.15)
    return list(agg.values())


def load_player_stats(force_refresh: bool = False) -> dict:
    """Return cached WC player stats, aggregating from ESPN when needed."""
    if CACHE_FILE.exists() and not force_refresh:
        return json.loads(CACHE_FILE.read_text())
    try:
        players = _aggregate(_completed_event_ids())
        result = {
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "players": players,
            "source": "espn",
        }
        CACHE_DIR.mkdir(exist_ok=True)
        CACHE_FILE.write_text(json.dumps(result))
        return result
    except Exception as exc:
        return {"fetched_at": None, "players": [], "source": "error", "error": str(exc)}


def clear_cache() -> None:
    CACHE_FILE.unlink(missing_ok=True)
