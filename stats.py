"""Match roster players to World Cup scorer stats and build the tracking table."""

import unicodedata

import pandas as pd

# Roster nation spelling -> ESPN national-team name (for match disambiguation).
NATION_ALIASES = {
    "USA": "United States",
}

# Per-player stats aggregated from ESPN match box scores.
STAT_COLUMNS = [
    "Apps", "Sub", "Goals", "Assists", "Shots", "SOG",
    "Yellow", "Red", "Fouls", "Fouled", "Offsides", "Own Goals", "Saves", "Conceded",
]


def _normalize(text: str) -> str:
    """Lowercase, strip accents and punctuation for fuzzy name comparison."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return "".join(c for c in text.lower() if c.isalnum() or c.isspace()).strip()


def _last_name(full_name: str) -> str:
    norm = _normalize(full_name)
    return norm.split()[-1] if norm else ""


def _index_stats(records: list[dict]) -> dict:
    """Index normalized scorer records by last name for matching."""
    index: dict[str, list[dict]] = {}
    for rec in records:
        rec = dict(rec)
        rec["_full"] = _normalize(rec.get("name", ""))
        rec["_nationality"] = _normalize(rec.get("nationality", ""))
        index.setdefault(_last_name(rec.get("name", "")), []).append(rec)
    return index


def _pick_match(row: pd.Series, candidates: list[dict]) -> dict | None:
    """Choose the best stat record for a roster row among same-last-name hits."""
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    nation = _normalize(NATION_ALIASES.get(row["Nation"], row["Nation"]))
    by_nation = [c for c in candidates if c["_nationality"] == nation]
    if len(by_nation) == 1:
        return by_nation[0]

    full = _normalize(row["Player"])
    by_full = [c for c in (by_nation or candidates) if c["_full"] == full]
    if by_full:
        return by_full[0]

    return (by_nation or candidates)[0]


def build_table(
    roster: pd.DataFrame,
    records: list[dict],
    crest_map: dict | None = None,
    headshot_map: dict | None = None,
    club_map: dict | None = None,
) -> pd.DataFrame:
    """Merge roster with WC scorer stats and add derived performance metrics."""
    index = _index_stats(records)
    df = roster.copy()

    extracted = []
    matched_flags = []
    for _, row in df.iterrows():
        match = _pick_match(row, index.get(_last_name(row["Player"]), []))
        if match:
            extracted.append({c: match.get(c, 0) or 0 for c in STAT_COLUMNS})
            matched_flags.append(True)
        else:
            extracted.append({c: 0 for c in STAT_COLUMNS})
            matched_flags.append(False)

    stats_df = pd.DataFrame(extracted)
    df = pd.concat([df.reset_index(drop=True), stats_df], axis=1)
    df["Matched"] = matched_flags

    df["Crest"] = df["Nation"].map(crest_map or {}).fillna("")
    df["Headshot"] = df["Player"].map(headshot_map or {}).fillna("")
    df["ClubCrest"] = df["Club"].map(club_map or {}).fillna("")

    return df
