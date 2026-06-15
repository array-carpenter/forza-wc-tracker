"""FORZA CALCIO — 2026 World Cup tracker for Serie A's exported players."""

import pandas as pd
import streamlit as st

import api_client
from roster import load_roster
from stats import build_table

st.set_page_config(
    page_title="FORZA CALCIO — World Cup Tracker",
    page_icon="⚽",
    layout="wide",
)

@st.cache_data(show_spinner="Fetching World Cup stats…")
def get_data(refresh_token: int) -> tuple[pd.DataFrame, dict]:
    payload = api_client.load_player_stats()
    roster = load_roster()
    table = build_table(roster, payload.get("players", []))
    return table, payload


def data_status_banner(payload: dict, matched: int, total: int) -> None:
    source = payload.get("source")
    if source == "api":
        st.success(
            f"Live data loaded {payload.get('fetched_at', '')} · all {total} "
            f"players listed · {matched} on the scoresheet so far."
        )
    elif source == "no_key":
        st.warning(
            "No token set — showing the roster with empty stats. Add "
            "`FOOTBALL_DATA_TOKEN` to `.streamlit/secrets.toml` (free token at "
            "football-data.org), then hit **Refresh stats**."
        )
    elif source == "error":
        st.error(f"Couldn't reach the stats API: {payload.get('error')}")
    else:
        st.info("No stats yet — the table will fill in as the tournament plays out.")


def player_card(row: pd.Series) -> None:
    st.markdown(f"**{row['Player']}**  \n{row['Nation']} · {row['Club']}")
    st.caption(f"{row['Position']} · {int(row['Apps'])} apps")
    c1, c2, c3 = st.columns(3)
    c1.metric("Goals", int(row["Goals"]))
    c2.metric("Assists", int(row["Assists"]))
    c3.metric("G+A", int(row["G+A"]))


def main() -> None:
    st.title("⚽ FORZA CALCIO — 2026 World Cup Tracker")
    st.caption("Serie A's exported talent, tracked through the 2026 World Cup.")

    if "refresh_token" not in st.session_state:
        st.session_state.refresh_token = 0

    with st.sidebar:
        st.header("Controls")
        if st.button("🔄 Refresh stats", width="stretch"):
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
        only_matched = st.checkbox("Only players with live stats", value=False)

    filtered = df.copy()
    if search:
        filtered = filtered[filtered["Player"].str.contains(search, case=False, na=False)]
    if nations:
        filtered = filtered[filtered["Nation"].isin(nations)]
    if clubs:
        filtered = filtered[filtered["Club"].isin(clubs)]
    if positions:
        filtered = filtered[filtered["Position"].isin(positions)]
    if only_matched:
        filtered = filtered[filtered["Matched"]]

    data_status_banner(payload, int(df["Matched"].sum()), len(df))

    # ---- Top performers ----
    st.subheader("🏆 Top performers")
    rank_metric = st.radio(
        "Rank by",
        ["Score", "G+A", "Goals", "Assists"],
        horizontal=True,
        label_visibility="collapsed",
    )
    top = filtered.sort_values(rank_metric, ascending=False).head(4)
    if top[rank_metric].max() == 0:
        st.info("No goal contributions logged yet — cards light up once the matches start.")
    else:
        cols = st.columns(len(top) if len(top) else 1)
        for col, (_, row) in zip(cols, top.iterrows()):
            with col:
                with st.container(border=True):
                    player_card(row)

    st.divider()

    # ---- Sortable / filterable table ----
    st.subheader(f"📋 All players ({len(filtered)})")
    sort_col, dir_col = st.columns([3, 1])
    table_cols = ["Apps", "Goals", "Assists", "Penalties", "G+A", "Score"]
    sort_by = sort_col.selectbox("Sort by", table_cols + ["Player", "Nation", "Club"], index=1)
    ascending = dir_col.selectbox("Order", ["Descending", "Ascending"]) == "Ascending"

    display = filtered.sort_values(sort_by, ascending=ascending)
    show_cols = ["Player", "Nation", "Club", "Position"] + table_cols
    st.dataframe(
        display[show_cols],
        width="stretch",
        hide_index=True,
        height=560,
        column_config={
            "Score": st.column_config.NumberColumn(format="%.1f"),
        },
    )
    st.caption("Tip: click any column header in the table to sort it directly.")


if __name__ == "__main__":
    main()
