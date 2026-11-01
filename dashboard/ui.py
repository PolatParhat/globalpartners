"""Look and feel shared by the six pages: colors, chart style, number formats.

Colors come from a validated categorical palette (colorblind-safe for adjacent slots). A color belongs to an
ENTITY, not to a rank: VIP is always blue, a loyalty member always blue, so a filter never repaints the survivors.
Because three of the colors are light on a white page, every chart has a visible legend and a table next to it.
"""
import plotly.graph_objects as go
import streamlit as st

from dashboard import data

BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e6e5e1"

SEGMENT_COLORS = {"VIP": BLUE, "Regular": ORANGE, "New": AQUA, "Churn Risk": YELLOW}
TIER_COLORS = {"High": "#184f95", "Medium": "#5598e7", "Low": "#b7d3f6"}          # one hue, dark = more value
STATUS_COLORS = {"active": "#0ca30c", "at_risk": "#fab219", "lapsed": "#d03b3b"}   # reserved status colors
STATUS_LABELS = {"active": "Active", "at_risk": "At risk", "lapsed": "Lapsed"}
GROUP_COLORS = {"Loyalty member": BLUE, "Not a member": ORANGE}
SEQUENTIAL_BLUE = [[0.0, "#cde2fb"], [0.5, "#5598e7"], [1.0, "#0d366b"]]


def money(value: float, cents: bool = False) -> str:
    return "–" if value != value else f"${value:,.2f}" if cents else f"${value:,.0f}"


def percent(value: float, digits: int = 0) -> str:
    return "–" if value != value else f"{value:.{digits}%}"


def number(value: float) -> str:
    return "–" if value != value else f"{value:,.0f}"


def style(fig: go.Figure, height: int = 360, legend: bool = True, y_title: str | None = None,
          x_title: str | None = None) -> go.Figure:
    """One chart style: white surface, light horizontal grid, no chart title (the section heading is the title),
    legend above the plot, labels in dark ink."""
    fig.update_layout(
        height=height, margin=dict(l=8, r=8, t=36 if legend else 12, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=MUTED, size=13), showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0, title_text=""),
        hoverlabel=dict(font_size=13), bargap=0.35,
    )
    fig.update_xaxes(showgrid=False, linecolor=GRID, title_text=x_title, zeroline=False)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, title_text=y_title)
    return fig


def show(fig: go.Figure, **kwargs) -> None:
    st.plotly_chart(style(fig, **kwargs), width="stretch", config={"displayModeBar": False})


def table(df, **column_config) -> None:
    """The table view that goes with a chart (also the accessible alternative to the colors)."""
    st.dataframe(df, hide_index=True, width="stretch", column_config=column_config or None)


def page_header(title: str, question: str) -> None:
    st.title(title)
    st.caption(question)


def as_of_note(as_of) -> None:
    st.caption(f"Customer figures are as of **{as_of:%d %b %Y}** (change the date in the sidebar). "
               "Customers = known customers; guests and the one faulty account are not counted.")


def data_limitation(text: str) -> None:
    st.info(text, icon=":material/info:")


def as_of_selector() -> None:
    """Sidebar date picker: the day the customer pages describe (CLV, segments and churn evolve daily)."""
    first, last = data.snapshot_range()
    if "as_of" not in st.session_state:
        st.session_state["as_of"] = last
    st.sidebar.date_input("Customer figures as of", min_value=first, max_value=last, key="as_of",
                          help="The customer snapshot keeps one row per customer per day, so you can look at any past day.")


def as_of_date():
    """The day chosen in the sidebar (the last loaded day if nothing was chosen yet)."""
    if "as_of" not in st.session_state:
        st.session_state["as_of"] = data.snapshot_range()[1]
    return st.session_state["as_of"]
