"""Load and clean the FORZA CALCIO player roster."""

from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).parent / "data"
ROSTER_RAW = DATA_DIR / "roster_raw.csv"

# Fix source-sheet spelling so nation matching against the API works.
NATION_FIXES = {
    "Ecudaor": "Ecuador",
}

# Correct misspelled names from the source sheet (display + data matching).
PLAYER_FIXES = {
    "Marucs Thuram": "Marcus Thuram",
    "Glieson Bremer": "Gleison Bremer",
    "Martin Butarina": "Martín Baturina",
}


def load_roster(path: Path = ROSTER_RAW) -> pd.DataFrame:
    """Read the roster sheet, skipping its empty header padding.

    The exported Google Sheet has six blank rows before the real header,
    so we find the 'Player' header row and parse from there.
    """
    raw = pd.read_csv(path, header=None, dtype=str, keep_default_na=False)

    header_idx = raw.index[raw[0].str.strip() == "Player"]
    if len(header_idx) == 0:
        raise ValueError("Could not find the 'Player' header row in the roster.")
    start = header_idx[0]

    df = raw.iloc[start + 1 :].copy()
    df.columns = raw.iloc[start].str.strip().tolist()

    df = df[df["Player"].str.strip() != ""].reset_index(drop=True)
    for col in df.columns:
        df[col] = df[col].str.strip()

    df["Nation"] = df["Nation"].replace(NATION_FIXES)
    df["Player"] = df["Player"].replace(PLAYER_FIXES)
    return df


if __name__ == "__main__":
    r = load_roster()
    print(r.head())
    print(f"\n{len(r)} players across {r['Nation'].nunique()} nations.")
