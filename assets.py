"""Resolve national-team crests and player headshots, cached to disk.

Crests come from football-data.org (the same token as the stats). Headshots
come from TheSportsDB's free tier, looked up once per player by name and
cached so the deployed app never re-queries.
"""

import base64
import json
import mimetypes
import time
import unicodedata
from pathlib import Path

import requests

DATA_DIR = Path(__file__).parent / "data"
CRESTS_FILE = DATA_DIR / "crests.json"
HEADSHOTS_FILE = DATA_DIR / "headshots.json"
HEADSHOTS_MANUAL_FILE = DATA_DIR / "headshots_manual.json"

UA = {"User-Agent": "Mozilla/5.0"}
WIKI_UA = {"User-Agent": "forza-wc-tracker/1.0 (personal project)"}
SPORTSDB_KEY = "3"  # free public test key

# Roster nation spelling -> football-data team name (for crest lookup).
# (Bosnia-Herzegovina already matches the API spelling exactly.)
NATION_TEAM_NAMES = {
    "Turkiye": "Turkey",
    "USA": "United States",
}


def _ascii(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in text if not unicodedata.combining(c))


# ---------------------------------------------------------------- crests ----
def build_crest_map(token: str | None, nations: list[str]) -> dict:
    """Build and cache {nation: crest_url} for the given roster nations."""
    if CRESTS_FILE.exists():
        cached = json.loads(CRESTS_FILE.read_text())
        if all(n in cached for n in nations):
            return cached
    if not token:
        return {}

    resp = requests.get(
        "https://api.football-data.org/v4/competitions/WC/teams",
        headers={"X-Auth-Token": token},
        timeout=20,
    )
    resp.raise_for_status()
    api = {t["name"].lower(): t.get("crest") for t in resp.json().get("teams", [])}

    out: dict[str, str] = {}
    for nation in nations:
        target = NATION_TEAM_NAMES.get(nation, nation).lower()
        match = api.get(target) or next(
            (c for nm, c in api.items() if target in nm or nm in target), None
        )
        if match:
            out[nation] = match

    DATA_DIR.mkdir(exist_ok=True)
    CRESTS_FILE.write_text(json.dumps(out))
    return out


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
