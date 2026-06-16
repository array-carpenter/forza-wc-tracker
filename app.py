"""FORZA CALCIO 2026 World Cup tracker for Serie A's exported players."""

import base64
import mimetypes
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

import api_client
import assets
from roster import load_roster
from stats import build_table

ASSETS = Path(__file__).parent / "assets"
WC_LOGO = ASSETS / "wc_2026_logo.png"
SPADE_LOGO = ASSETS / "spade_soccer_logo.png"
FORZA_LOGO = ASSETS / "forza_calcio_white.png"

# Kept local (not pulled from api_client) so a stale-module deploy can't crash
# app.py at import time.
REFRESH_TTL = 8 * 3600  # auto-refresh roughly 3x a day
REPORT_METRICS = [
    ("possessionPct", "Possession %"),
    ("totalShots", "Shots"),
    ("shotsOnTarget", "On target"),
    ("totalPasses", "Passes"),
    ("wonCorners", "Corners"),
    ("totalTackles", "Tackles"),
    ("foulsCommitted", "Fouls"),
]

st.set_page_config(
    page_title="FORZA CALCIO World Cup Tracker",
    page_icon=str(WC_LOGO),
    layout="wide",
)

SIDEBAR_BLUE = "#002bfc"


def _data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def build_style() -> str:
    return f"""
<style>
html, body, [class*="st-"], .stApp, .stApp * {{
    font-family: Helvetica, "Helvetica Neue", Arial, sans-serif !important;
}}
/* Uniform top-performer cards. */
.pcard {{
    border: 1px solid #e6e6e6; border-radius: 12px; background: #fff;
    padding: 18px 14px; text-align: center;
}}
.phead {{
    width: 88px; height: 88px; border-radius: 50%; object-fit: cover;
    object-position: top center; display: block; margin: 0 auto 12px; background: #f0f0f0;
}}
.pname {{
    font-weight: 700; font-size: 1rem; white-space: nowrap;
    overflow: hidden; text-overflow: ellipsis;
}}
.pmeta {{
    color: #555; font-size: 0.85rem; margin-top: 4px; white-space: nowrap;
    overflow: hidden; text-overflow: ellipsis;
}}
.picon {{ height: 15px; vertical-align: middle; margin-right: 5px; }}
.pstats {{ display: flex; justify-content: center; gap: 22px; margin-top: 16px; }}
.pnum {{ font-size: 1.7rem; font-weight: 700; line-height: 1; }}
.plbl {{
    font-size: 0.7rem; color: #808495; text-transform: uppercase;
    letter-spacing: 0.04em; margin-top: 4px;
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


@st.cache_data(ttl=REFRESH_TTL, show_spinner="Fetching World Cup stats…")
def get_data(refresh_token: int) -> tuple[pd.DataFrame, dict]:
    payload = api_client.load_player_stats()
    roster = load_roster()
    nations = sorted(roster["Nation"].unique())
    flag_map = _safe(assets.build_flag_map, nations)
    headshot_map = _safe(assets.resolve_headshots)
    club_map = _safe(assets.build_club_map, sorted(roster["Club"].unique()))
    table = build_table(roster, payload.get("players", []), flag_map, headshot_map, club_map)
    return table, payload


@st.cache_data(ttl=REFRESH_TTL, show_spinner=False)
def get_matches(refresh_token: int) -> list[dict]:
    try:
        return api_client.list_matches()
    except Exception:
        return []


@st.cache_data(ttl=REFRESH_TTL, show_spinner=False)
def get_match_report(event_id: str) -> dict | None:
    try:
        return api_client.match_report(event_id)
    except Exception:
        return None


def data_status_banner(payload: dict, matched: int, total: int) -> None:
    if payload.get("source") == "error":
        st.error(f"Couldn't reach the stats API: {payload.get('error')}")


def player_card(row: pd.Series) -> None:
    photo = row.get("Headshot") or row.get("Crest") or ""
    crest, club_crest = row.get("Crest") or "", row.get("ClubCrest") or ""
    head = f"<img class='phead' src='{photo}'>" if photo else "<div class='phead'></div>"
    flag = f"<img class='picon' src='{crest}'>" if crest else ""
    club = f"<img class='picon' src='{club_crest}'>" if club_crest else ""
    st.markdown(
        f"<div class='pcard'>{head}"
        f"<div class='pname'>{row['Player']}</div>"
        f"<div class='pmeta'>{flag}{row['Nation']}</div>"
        f"<div class='pmeta'>{club}{row['Club']} · {row['Position']}</div>"
        "<div class='pstats'>"
        f"<div><div class='pnum'>{int(row['Apps'])}</div><div class='plbl'>Apps</div></div>"
        f"<div><div class='pnum'>{int(row['Goals'])}</div><div class='plbl'>Goals</div></div>"
        f"<div><div class='pnum'>{int(row['Assists'])}</div><div class='plbl'>Assists</div></div>"
        "</div></div>",
        unsafe_allow_html=True,
    )


def shot_conversion_chart(df: pd.DataFrame) -> None:
    """Scatter of Goals vs Shots, bubble size = shots on target."""
    data = df[df["Shots"] > 0].copy()
    if data.empty:
        st.info("No shots logged yet — this lights up once your players start firing.")
        return

    base = alt.Chart(data).encode(
        x=alt.X("Shots:Q", title="Shots", scale=alt.Scale(zero=True, nice=True),
                axis=alt.Axis(format="d", tickMinStep=1)),
        y=alt.Y("Goals:Q", title="Goals", scale=alt.Scale(zero=True, nice=True),
                axis=alt.Axis(format="d", tickMinStep=1)),
    )
    sog_max = int(data["SOG"].max())
    sog_values = list(range(1, sog_max + 1)) or [1]
    points = base.mark_circle(opacity=0.8, stroke="white", strokeWidth=1).encode(
        size=alt.Size("SOG:Q", title="On target", scale=alt.Scale(range=[80, 900]),
                      legend=alt.Legend(format="d", values=sog_values)),
        color=alt.Color("Position:N", title="Position",
                        scale=alt.Scale(scheme="tableau10")),
        tooltip=[
            alt.Tooltip("Player:N"), alt.Tooltip("Nation:N"), alt.Tooltip("Club:N"),
            alt.Tooltip("Shots:Q"), alt.Tooltip("SOG:Q", title="On target"),
            alt.Tooltip("Goals:Q"), alt.Tooltip("Assists:Q"),
        ],
    )
    labels = (
        alt.Chart(data[(data["Goals"] > 0) | (data["Shots"] >= 4)])
        .mark_text(align="left", dx=10, dy=-2, fontSize=11, color="#333")
        .encode(x="Shots:Q", y="Goals:Q", text="Player:N")
    )
    chart = (points + labels).properties(height=460, width="container").interactive()
    st.altair_chart(chart, theme="streamlit")
    st.caption("Bubble size = shots on target. Hover for detail; scroll to zoom.")


def _num(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def match_report_chart(report: dict) -> None:
    """Back-to-back comparison bars of two teams' match stats."""
    home, away = report.get("home"), report.get("away")
    if not home or not away:
        st.info("No team stats available for this match.")
        return

    hc, _, ac = st.columns([3, 1, 3], vertical_alignment="center")
    hc.markdown(
        f"<div style='text-align:right;font-size:1.1rem;font-weight:700'>{home['name']} "
        f"<img src='{home['logo']}' height='30' style='vertical-align:middle'></div>",
        unsafe_allow_html=True,
    )
    ac.markdown(
        f"<div style='font-size:1.1rem;font-weight:700'>"
        f"<img src='{away['logo']}' height='30' style='vertical-align:middle'> {away['name']}</div>",
        unsafe_allow_html=True,
    )

    rows = []
    for key, label in REPORT_METRICS:
        hv, av = _num(home["stats"].get(key)), _num(away["stats"].get(key))
        total = hv + av or 1
        is_pct = key.endswith("Pct")
        fmt = (lambda x: f"{x:.1f}%") if is_pct else (lambda x: f"{int(round(x))}")
        rows.append({"Metric": label, "Team": home["name"], "x": -(hv / total),
                     "Value": hv, "Label": fmt(hv)})
        rows.append({"Metric": label, "Team": away["name"], "x": av / total,
                     "Value": av, "Label": fmt(av)})
    data = pd.DataFrame(rows)
    order = [label for _, label in REPORT_METRICS]
    color = alt.Color("Team:N", scale=alt.Scale(domain=[home["name"], away["name"]],
                                                 range=["#002bfc", "#ff6b35"]),
                      legend=None)

    bars = alt.Chart(data).mark_bar(height=20).encode(
        y=alt.Y("Metric:N", sort=order, title=None, axis=alt.Axis(labelFontWeight="bold")),
        x=alt.X("x:Q", title=None, axis=None, scale=alt.Scale(domain=[-1, 1])),
        color=color,
        tooltip=["Team:N", "Metric:N", alt.Tooltip("Value:Q")],
    )
    h_text = alt.Chart(data[data["Team"] == home["name"]]).mark_text(
        align="right", dx=-6, color="#333").encode(y=alt.Y("Metric:N", sort=order),
                                                    x="x:Q", text="Label:N")
    a_text = alt.Chart(data[data["Team"] == away["name"]]).mark_text(
        align="left", dx=6, color="#333").encode(y=alt.Y("Metric:N", sort=order),
                                                  x="x:Q", text="Label:N")
    chart = (bars + h_text + a_text).properties(height=300, width="container")
    st.altair_chart(chart, theme="streamlit")


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
            get_matches.clear()
            get_match_report.clear()
        st.caption("Auto-refreshes ~3x a day.")
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
        [m for m in ["Goals", "Assists", "Apps"] if m in filtered.columns],
        horizontal=True,
        label_visibility="collapsed",
    )
    top = filtered.sort_values(rank_metric, ascending=False).head(4)
    if len(top):
        cols = st.columns(len(top))
        for col, (_, row) in zip(cols, top.iterrows()):
            with col:
                player_card(row)

    st.divider()

    # ---- Sortable / filterable table ----
    st.subheader(f"All players ({len(filtered)})")
    # (column, short header, tooltip) for every stat ESPN gives us.
    stat_meta = [
        ("Apps", "Apps", "Appearances"),
        ("Sub", "Sub", "Substitute appearances"),
        ("Goals", "G", "Goals"),
        ("Assists", "A", "Assists"),
        ("Shots", "Sh", "Total shots"),
        ("SOG", "SOG", "Shots on goal"),
        ("Yellow", "YC", "Yellow cards"),
        ("Red", "RC", "Red cards"),
        ("Fouls", "FC", "Fouls committed"),
        ("Fouled", "FS", "Fouls suffered"),
        ("Offsides", "Off", "Offsides"),
        ("Own Goals", "OG", "Own goals"),
        ("Saves", "Sv", "Saves (goalkeeper)"),
        ("Conceded", "GA", "Goals conceded (goalkeeper)"),
    ]
    display = filtered.sort_values("Goals", ascending=False)
    base_cols = ["Headshot", "Player", "Crest", "Nation", "ClubCrest", "Club", "Position"]
    table_cols = [c for c, _, _ in stat_meta if c in display.columns]
    # Only request columns that exist (survives a partial module reload on deploy).
    show_cols = [c for c in base_cols + table_cols if c in display.columns]
    column_config = {
        "Headshot": st.column_config.ImageColumn(" "),
        "Crest": st.column_config.ImageColumn(" "),
        "ClubCrest": st.column_config.ImageColumn(" "),
    }
    for col, header, tip in stat_meta:
        if col in display.columns:
            column_config[col] = st.column_config.NumberColumn(header, help=tip, width="small")
    st.dataframe(
        display[show_cols],
        width="stretch",
        hide_index=True,
        height=560,
        column_config=column_config,
    )
    st.caption("Click any column header to sort by it.")

    st.divider()

    # ---- Shot conversion ----
    st.subheader("Shot conversion")
    shot_conversion_chart(filtered)

    st.divider()

    # ---- Match report ----
    st.subheader("Match report")
    matches = get_matches(st.session_state.refresh_token)
    if not matches:
        st.info("No completed matches yet.")
    else:
        labels = {
            f"{m['home']['name']} {m['home']['score']}–{m['away']['score']} "
            f"{m['away']['name']}  ({m['date']})": m["id"]
            for m in matches
        }
        pick = st.selectbox("Match", list(labels), index=len(labels) - 1)
        report = get_match_report(labels[pick])
        if report:
            match_report_chart(report)
        else:
            st.info("Couldn't load this match's stats.")


if __name__ == "__main__":
    main()
