"""Fetch 2026 World Cup scorer statistics from football-data.org.

The free tier covers the World Cup via its scorers board, which provides
matches played, goals, assists and penalties per player. There is no
minutes or rating data on this endpoint.

Get a free token at https://www.football-data.org/client/register and set it
as the FOOTBALL_DATA_TOKEN environment variable or in .streamlit/secrets.toml.
"""

import json
import os
import time
import unicodedata
from pathlib import Path

import requests

BASE_URL = "https://api.football-data.org/v4"
COMPETITION = "WC"  # FIFA World Cup
SCORERS_LIMIT = 200  # pull a deep board so we catch every roster player who scored

CACHE_DIR = Path(__file__).parent / "data"
CACHE_FILE = CACHE_DIR / "wc_players_cache.json"


def get_token() -> str | None:
    """Token from env var, falling back to Streamlit secrets if present."""
    token = os.environ.get("FOOTBALL_DATA_TOKEN")
    if token:
        return token.strip()
    try:
        import streamlit as st

        return st.secrets.get("FOOTBALL_DATA_TOKEN")
    except Exception:
        return None


def _normalize_record(entry: dict) -> dict:
    """Flatten one scorers entry into the app's normalized stat schema."""
    player = entry.get("player") or {}
    team = entry.get("team") or {}
    return {
        "name": player.get("name") or "",
        "nationality": player.get("nationality") or "",
        "team": team.get("name") or "",
        "Apps": entry.get("playedMatches") or 0,
        "Goals": entry.get("goals") or 0,
        "Assists": entry.get("assists") or 0,
        "Penalties": entry.get("penalties") or 0,
    }


def _fetch_scorers(token: str) -> list[dict]:
    resp = requests.get(
        f"{BASE_URL}/competitions/{COMPETITION}/scorers",
        headers={"X-Auth-Token": token},
        params={"limit": SCORERS_LIMIT},
        timeout=20,
    )
    resp.raise_for_status()
    payload = resp.json()
    return [_normalize_record(e) for e in payload.get("scorers", [])]


def load_player_stats(force_refresh: bool = False) -> dict:
    """Return cached WC scorer stats, fetching from the API when needed.

    Shape: {"fetched_at": iso, "players": [...], "source": ...}.
    Falls back to an empty payload (so the app still renders the roster) when
    no token is set or the request fails.
    """
    if CACHE_FILE.exists() and not force_refresh:
        return json.loads(CACHE_FILE.read_text())

    token = get_token()
    if not token:
        return {"fetched_at": None, "players": [], "source": "no_key"}

    try:
        players = _fetch_scorers(token)
        result = {
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "players": players,
            "source": "api",
        }
        CACHE_DIR.mkdir(exist_ok=True)
        CACHE_FILE.write_text(json.dumps(result))
        return result
    except Exception as exc:  # network/quota/parse failures shouldn't crash the app
        return {"fetched_at": None, "players": [], "source": "error", "error": str(exc)}


def clear_cache() -> None:
    CACHE_FILE.unlink(missing_ok=True)
