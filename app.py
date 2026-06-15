"""FORZA CALCIO 2026 World Cup tracker for Serie A's exported players."""

import base64
import mimetypes
from pathlib import Path

import pandas as pd
import streamlit as st

import api_client
import assets
from roster import load_roster
from stats import build_table

ASSETS = Path(__file__).parent / "assets"
FONTS = ASSETS / "fonts"
WC_LOGO = ASSETS / "wc_2026_logo.png"
SPADE_LOGO = ASSETS / "spade_soccer_logo.png"
FORZA_LOGO = ASSETS / "forza_calcio_white.png"

st.set_page_config(
    page_title="FORZA CALCIO World Cup Tracker",
    page_icon=str(WC_LOGO),
    layout="wide",
)

SIDEBAR_BLUE = "#002bfc"


def _data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def _lp_font_face() -> str:
    """Embed the LP Brighter Side Demo font if its file is in assets/fonts/."""
    if not FONTS.exists():
        return ""
    for f in FONTS.iterdir():
        if "brighter" in f.name.lower() and f.suffix.lower() in (".ttf", ".otf", ".woff", ".woff2"):
            fmt = {"ttf": "truetype", "otf": "opentype"}.get(f.suffix.lower().lstrip("."), "woff2")
            return (
                "@font-face { font-family: 'LP Brighter Side Demo'; "
                f"src: url('{_data_uri(f)}') format('{fmt}'); }}"
            )
    return ""


def build_style() -> str:
    return f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Abril+Fatface&display=swap');
{_lp_font_face()}
html, body, [class*="st-"], .stApp, .stApp * {{
    font-family: Helvetica, "Helvetica Neue", Arial, sans-serif !important;
}}
/* Primary title + secondary headings use the brand display fonts. */
.stApp h1, .stApp h1 * {{
    font-family: 'LP Brighter Side Demo', 'Abril Fatface', serif !important;
}}
.stApp h2, .stApp h3, .stApp h2 *, .stApp h3 * {{
    font-family: 'Abril Fatface', 'Abril Display', serif !important;
}}
/* Keep Streamlit's Material icon ligatures on their icon font. */
[data-testid="stIconMaterial"],
span[class*="material-symbols"],
span[class*="material-icons"],
.material-symbols-rounded, .material-symbols-outlined, .material-icons {{
    font-family: 'Material Symbols Rounded', 'Material Symbols Outlined',
        'Material Icons' !important;
}}
/* Sidebar: deep-blue panel, white text, white input bars. */
[data-testid="stSidebar"] {{ background-color: {SIDEBAR_BLUE} !important; }}
[data-testid="stSidebar"] * {{ color: #ffffff !important; }}
[data-testid="stSidebar"] hr {{ border-color: rgba(255, 255, 255, 0.4) !important; }}
[data-testid="stSidebar"] input,
[data-testid="stSidebar"] textarea,
[data-testid="stSidebar"] [data-baseweb="select"] > div {{ background-color: #ffffff !important; }}
[data-testid="stSidebar"] input,
[data-testid="stSidebar"] textarea,
[data-testid="stSidebar"] [data-baseweb="select"] * {{ color: #111111 !important; }}
[data-testid="stSidebar"] .stButton button,
[data-testid="stSidebar"] .stButton button * {{
    background-color: #ffffff !important;
    color: {SIDEBAR_BLUE} !important;
    border: none !important;
}}
</style>
"""


def _safe(fn, *args) -> dict:
    """Resolve an asset map, degrading to no-images rather than crashing."""
    try:
        return fn(*args) or {}
    except Exception:
        return {}


@st.cache_data(show_spinner="Fetching World Cup stats…")
def get_data(refresh_token: int) -> tuple[pd.DataFrame, dict]:
    payload = api_client.load_player_stats()
    roster = load_roster()
    nations = sorted(roster["Nation"].unique())
    flag_map = _safe(assets.build_flag_map, nations)
    headshot_map = _safe(assets.resolve_headshots)
    club_map = _safe(assets.build_club_map, sorted(roster["Club"].unique()))
    table = build_table(roster, payload.get("players", []), flag_map, headshot_map, club_map)
    return table, payload


def data_status_banner(payload: dict, matched: int, total: int) -> None:
    source = payload.get("source")
    if source == "no_key":
        st.warning(
            "No token set. Showing the roster with empty stats. Add "
            "`FOOTBALL_DATA_TOKEN` to `.streamlit/secrets.toml` (free token at "
            "football-data.org), then hit **Refresh stats**."
        )
    elif source == "error":
        st.error(f"Couldn't reach the stats API: {payload.get('error')}")


def player_card(row: pd.Series) -> None:
    photo, crest, club_crest = row.get("Headshot"), row.get("Crest"), row.get("ClubCrest")
    pic_col, name_col = st.columns([1, 2], vertical_alignment="center")
    with pic_col:
        if photo:
            st.image(photo, width="stretch")
        elif crest:
            st.image(crest, width=64)
    with name_col:
        crest_img = (
            f"<img src='{crest}' height='18' style='vertical-align:middle'> " if crest else ""
        )
        club_img = (
            f"<img src='{club_crest}' height='15' style='vertical-align:middle'> "
            if club_crest else ""
        )
        st.markdown(f"**{row['Player']}**")
        st.markdown(f"{crest_img}{row['Nation']}", unsafe_allow_html=True)
        st.markdown(
            f"<span style='color:#808495;font-size:0.85rem'>{club_img}{row['Club']} · "
            f"{row['Position']} · {int(row['Apps'])} apps</span>",
            unsafe_allow_html=True,
        )
    c1, c2 = st.columns(2)
    c1.metric("Goals", int(row["Goals"]))
    c2.metric("Assists", int(row["Assists"]))


def app_header() -> None:
    st.markdown(build_style(), unsafe_allow_html=True)

    # Collaboration banner: The Spade x FORZA CALCIO (white logos on brand blue).
    if SPADE_LOGO.exists() and FORZA_LOGO.exists():
        st.markdown(
            f"<div style='background:{SIDEBAR_BLUE};border-radius:14px;padding:16px 24px;"
            "display:flex;align-items:center;justify-content:center;gap:28px;"
            "margin-bottom:14px;'>"
            f"<img src='{_data_uri(SPADE_LOGO)}' style='height:56px;'>"
            "<span style='color:#fff;font-size:30px;font-weight:300;'>&times;</span>"
            f"<img src='{_data_uri(FORZA_LOGO)}' style='height:56px;'></div>",
            unsafe_allow_html=True,
        )

    left, mid = st.columns([1, 7], vertical_alignment="center")
    with left:
        if WC_LOGO.exists():
            st.image(str(WC_LOGO), width="stretch")
    with mid:
        st.title("FORZA CALCIO 2026 World Cup Tracker")
        st.caption(
            "Forza Calcio and The Spade present a Serie A/B World Cup Player Stats Tracker"
        )


def main() -> None:
    app_header()

    if "refresh_token" not in st.session_state:
        st.session_state.refresh_token = 0

    with st.sidebar:
        st.header("Controls")
        if st.button("Refresh stats", width="stretch"):
            api_client.clear_cache()
            st.session_state.refresh_token += 1
            get_data.clear()
        st.divider()

    df, payload = get_data(st.session_state.refresh_token)

    # ---- Sidebar filters ----
    with st.sidebar:
        st.subheader("Filters")
        search = st.text_input("Search player")
        nations = st.multiselect("Nation", sorted(df["Nation"].unique()))
        clubs = st.multiselect("Club", sorted(df["Club"].unique()))
        positions = st.multiselect("Position", sorted(df["Position"].unique()))

    filtered = df.copy()
    if search:
        filtered = filtered[filtered["Player"].str.contains(search, case=False, na=False)]
    if nations:
        filtered = filtered[filtered["Nation"].isin(nations)]
    if clubs:
        filtered = filtered[filtered["Club"].isin(clubs)]
    if positions:
        filtered = filtered[filtered["Position"].isin(positions)]

    data_status_banner(payload, int(df["Matched"].sum()), len(df))

    # ---- Top performers ----
    st.subheader("Top performers")
    rank_metric = st.radio(
        "Rank by",
        ["Goals", "Assists"],
        horizontal=True,
        label_visibility="collapsed",
    )
    top = filtered.sort_values(rank_metric, ascending=False).head(4)
    if len(top):
        cols = st.columns(len(top))
        for col, (_, row) in zip(cols, top.iterrows()):
            with col:
                with st.container(border=True):
                    player_card(row)

    st.divider()

    # ---- Sortable / filterable table ----
    st.subheader(f"All players ({len(filtered)})")
    table_cols = ["Apps", "Goals", "Assists", "Yellow", "Red"]
    display = filtered.sort_values("Goals", ascending=False)
    show_cols = (
        ["Headshot", "Player", "Crest", "Nation", "ClubCrest", "Club", "Position"] + table_cols
    )
    st.dataframe(
        display[show_cols],
        width="stretch",
        hide_index=True,
        height=560,
        column_config={
            "Headshot": st.column_config.ImageColumn(" "),
            "Crest": st.column_config.ImageColumn(" "),
            "ClubCrest": st.column_config.ImageColumn(" "),
            "Yellow": st.column_config.NumberColumn("YC", help="Yellow cards"),
            "Red": st.column_config.NumberColumn("RC", help="Red cards"),
        },
    )
    st.caption("Click any column header to sort by it.")


if __name__ == "__main__":
    main()
