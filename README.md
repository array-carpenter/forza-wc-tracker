# FORZA CALCIO — 2026 World Cup Tracker

A Streamlit app that tracks Serie A's exported players through the 2026 World
Cup. Top-performer cards sit on top; a filterable, sortable table sits below.

## What it does

- Loads the player roster from `data/roster_raw.csv` (the exported FORZA CALCIO sheet).
- Auto-fetches World Cup scorer stats from
  [football-data.org](https://www.football-data.org/) and matches them to the
  roster by accent-normalized name + nationality.
- Tracks **Apps** (matches played), **Goals**, **Assists**, **Penalties**, plus
  derived **G+A** and a composite **Score**.
- Filters by nation, club, position, and free-text search; sorts by any stat.
- Caches the API pull to disk; a **Refresh stats** button re-pulls.

## Setup

```bash
uv venv --python 3.13
uv pip install -r requirements.txt
```

Add your free football-data.org token:

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# then edit secrets.toml and paste your token
```

(Or set `FOOTBALL_DATA_TOKEN` in your environment.)

## Run

```bash
.venv/bin/streamlit run app.py
```

The app runs without a token too — it shows the roster with empty stats and a
banner, then fills in once a token is set and you click **Refresh stats**.

## Files

| File | Role |
|------|------|
| `roster.py` | Parse + clean the roster sheet |
| `api_client.py` | Fetch + cache World Cup scorer stats |
| `stats.py` | Match roster ↔ stats, compute derived metrics |
| `app.py` | Streamlit UI |

## Data-source notes

- World Cup competition code is `WC`; the 2026 edition runs June 11 – July 19, 2026.
- football-data.org's **free** World Cup data is the **scorers board**: it covers
  goals, penalties, and matches played, and only lists players who have scored.
  A roster player shows up the moment they score; until then they sit at zero.
- **Assists are not published** for the World Cup on this source, so the Assists
  column stays at 0. Goals/apps/penalties are the live signal.
- Rate limit is ~10 requests/minute (no hard daily cap). The disk cache means a
  normal session makes one request.
