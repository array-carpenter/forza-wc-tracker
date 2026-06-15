# FORZA CALCIO 2026 World Cup Tracker

A Streamlit app that tracks Serie A's exported players through the 2026 World
Cup. Top-performer cards sit on top; a filterable, sortable table sits below.

A collaboration between Forza Calcio and The Spade.

## What it does

- Loads the player roster from `data/roster_raw.csv` (the exported FORZA CALCIO sheet).
- Auto-fetches per-player World Cup stats from
  [ESPN's free API](https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard)
  by aggregating every completed match's box score, and matches them to the
  roster by accent-normalized name. **No API key required.**
- Tracks **Apps** (matches played), **Goals**, **Assists**, **Yellow**, and **Red**
  cards for every player who features, not just scorers.
- Shows **circular nation flags** (circle-flags), **club badges** (TheSportsDB,
  with a hand-picked black Juventus badge), and **player headshots**
  (TheSportsDB → Wikipedia, with hand-picked overrides).
- Filters by nation, club, position, and free-text search; sorts by any stat.
- Caches the fetch to disk; a **Refresh stats** button re-pulls.

## Setup

```bash
uv venv --python 3.13
uv pip install -r requirements.txt
```

No keys or secrets needed — every data source is free and keyless.

## Run

```bash
.venv/bin/streamlit run app.py
```

## Files

| File | Role |
|------|------|
| `roster.py` | Parse + clean the roster sheet (incl. name/nation fixes) |
| `api_client.py` | Aggregate per-player stats from ESPN's match box scores |
| `assets.py` | Resolve + cache flags, club badges, and player headshots |
| `stats.py` | Match roster ↔ stats, compute derived metrics |
| `app.py` | Streamlit UI |

To pin a specific headshot for any player, add an entry to
`data/headshots_manual.json`, either an image URL or a path to a file bundled
under `assets/headshots/` (handy when a source blocks hotlinking). Club-badge
overrides live in `assets.CLUB_OVERRIDE`.

## Data-source notes

- The 2026 World Cup runs June 11 – July 19, 2026. ESPN's league code is `fifa.world`.
- Stats are aggregated from each completed match's roster box score, so a player
  appears the moment their nation plays — appearances, goals, assists, and cards
  all populate, regardless of whether they've scored.
- The on-disk cache (`data/wc_players_cache.json`, gitignored) is refreshed on a
  cold start or when you click **Refresh stats**.
