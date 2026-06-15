"""Resolve national-team flags and player headshots.

Flags are circular icons from circle-flags (hatscripts), addressed by ISO
country code, so the mapping is deterministic and needs no API. Headshots
come from TheSportsDB's free tier (Wikipedia fallback), looked up once per
player by name and cached so the deployed app never re-queries.
"""

import base64
import json
import mimetypes
import time
import unicodedata
from pathlib import Path

import requests

DATA_DIR = Path(__file__).parent / "data"
HEADSHOTS_FILE = DATA_DIR / "headshots.json"
HEADSHOTS_MANUAL_FILE = DATA_DIR / "headshots_manual.json"

UA = {"User-Agent": "Mozilla/5.0"}
WIKI_UA = {"User-Agent": "forza-wc-tracker/1.0 (personal project)"}
SPORTSDB_KEY = "3"  # free public test key

FLAG_BASE = "https://hatscripts.github.io/circle-flags/flags/{code}.svg"

# Roster nation spelling -> ISO 3166-1 alpha-2 (gb-sct for Scotland).
NATION_ISO = {
    "Algeria": "dz", "Argentina": "ar", "Australia": "au", "Austria": "at",
    "Belgium": "be", "Bosnia-Herzegovina": "ba", "Brazil": "br", "Canada": "ca",
    "Colombia": "co", "Croatia": "hr", "Ecuador": "ec", "France": "fr",
    "Iraq": "iq", "Ivory Coast": "ci", "Japan": "jp", "Mexico": "mx",
    "Morocco": "ma", "Netherlands": "nl", "Norway": "no", "Paraguay": "py",
    "Portugal": "pt", "Scotland": "gb-sct", "Senegal": "sn", "Sweden": "se",
    "Switzerland": "ch", "Turkiye": "tr", "USA": "us", "Uruguay": "uy",
}


def _ascii(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in text if not unicodedata.combining(c))


# ----------------------------------------------------------------- flags ----
def build_flag_map(nations: list[str]) -> dict:
    """Return {nation: circular-flag-url} for the given roster nations."""
    return {n: FLAG_BASE.format(code=NATION_ISO[n]) for n in nations if n in NATION_ISO}


# ------------------------------------------------------------- headshots ----
def _sportsdb_headshot(name: str, club: str) -> str | None:
    """Find a headshot on TheSportsDB, preferring a club match."""
    try:
        r = requests.get(
            f"https://www.thesportsdb.com/api/v1/json/{SPORTSDB_KEY}/searchplayers.php",
            params={"p": _ascii(name)},
            headers=UA,
            timeout=15,
        )
        if r.status_code != 200:
            return None
        players = [p for p in (r.json().get("player") or []) if p.get("strSport") == "Soccer"]
        if not players:
            return None
        best = next(
            (p for p in players if club.lower() in (p.get("strTeam") or "").lower()),
            players[0],
        )
        return best.get("strThumb") or best.get("strCutout") or best.get("strRender") or None
    except Exception:
        return None


def _wikipedia_headshot(name: str) -> str | None:
    """Fall back to a Wikipedia page thumbnail, checking it's a footballer."""
    for query in (name, f"{name} footballer"):
        title = _ascii(query).replace(" ", "_")
        try:
            r = requests.get(
                f"https://en.wikipedia.org/api/rest_v1/page/summary/{title}",
                headers=WIKI_UA,
                timeout=15,
            )
            if r.status_code != 200:
                continue
            j = r.json()
            thumb = (j.get("thumbnail") or {}).get("source")
            desc = (j.get("description") or "").lower()
            if thumb and ("football" in desc or "soccer" in desc or query.endswith("footballer")):
                return thumb
        except Exception:
            continue
    return None


def _search_headshot(name: str, club: str) -> str | None:
    return _sportsdb_headshot(name, club) or _wikipedia_headshot(name)


def build_headshot_map(players: list[tuple[str, str]]) -> dict:
    """Build/extend {player_name: headshot_url} for (name, club) pairs.

    Only looks up names not already cached, so it's cheap on re-runs.
    Hand-picked URLs in headshots_manual.json always win.
    """
    cache: dict[str, str] = {}
    if HEADSHOTS_FILE.exists():
        cache = json.loads(HEADSHOTS_FILE.read_text())

    changed = False
    for name, club in players:
        if cache.get(name):
            continue
        url = _search_headshot(name, club)
        cache[name] = url or ""
        changed = True
        time.sleep(2.0)  # free tier throttles fast bursts; keep under ~30/min

    if changed:
        DATA_DIR.mkdir(exist_ok=True)
        HEADSHOTS_FILE.write_text(json.dumps(cache))

    return resolve_headshots(cache)


def _to_src(value: str) -> str:
    """Pass through http URLs; embed local image files as data URIs.

    Manual overrides may point at a bundled file (e.g. a clean cutout whose
    host blocks hotlinking). Embedding it makes the image render anywhere.
    """
    if not value or value.startswith(("http://", "https://", "data:")):
        return value
    path = Path(__file__).parent / value
    if not path.exists():
        return ""
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    data = base64.b64encode(path.read_bytes()).decode()
    return f"data:{mime};base64,{data}"


def resolve_headshots(cache: dict | None = None) -> dict:
    """Merge the auto cache with hand-picked overrides (overrides win)."""
    if cache is None:
        cache = json.loads(HEADSHOTS_FILE.read_text()) if HEADSHOTS_FILE.exists() else {}
    merged = dict(cache)
    if HEADSHOTS_MANUAL_FILE.exists():
        for name, url in json.loads(HEADSHOTS_MANUAL_FILE.read_text()).items():
            if url:
                merged[name] = _to_src(url)
    return merged
