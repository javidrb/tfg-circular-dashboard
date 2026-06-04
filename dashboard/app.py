"""
Dashboard interactivo para la simulación de escenarios de economía circular.

Lanzamiento:
    streamlit run dashboard/app.py
"""
from __future__ import annotations

# --- Path bootstrap --------------------------------------------------------- #
import sys
from pathlib import Path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
# --------------------------------------------------------------------------- #

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard.data_loader import (
    DataBundle,
    aggregate_indicator,
    comparison_breakdown,
    delta_vs_baseline,
    filter_data,
    load_all,
    total_indicator,
)
from dashboard.sensitivity import elasticity_table, important_sectors, tornado_data

# ============================================================================
# Configuración general y branding
# ============================================================================

st.set_page_config(
    page_title="Dashboard Economía Circular | TFG",
    page_icon="♻️",
    layout="wide",
    initial_sidebar_state="expanded",
)

PALETTE = {
    "baseline":   "#94A3B8",
    "scenario":   "#1D4ED8",   # blue-700, más sobrio
    "positive":   "#059669",   # emerald-600
    "negative":   "#DC2626",   # red-600
    "neutral":    "#94A3B8",
    "accent":     "#EA580C",   # orange-600
    "subtle":     "#F1F5F9",
    "text":       "#0F172A",
    "text_muted": "#64748B",
    "border":     "#E2E8F0",
}

CUSTOM_CSS = f"""
<style>
/* --- Tipografía y layout general --- */
.block-container {{padding-top: 1.2rem; padding-bottom: 2.5rem; max-width: 1400px;}}
html, body, [class*="css"] {{font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;}}
h1, h2, h3, h4 {{color: {PALETTE["text"]}; letter-spacing: -0.01em;}}
h1 {{font-weight: 700;}}
h2 {{font-weight: 650;}}
h3 {{font-weight: 600;}}

/* --- KPIs (st.metric) --- */
[data-testid="stMetric"] {{
    background: white;
    border: 1px solid {PALETTE["border"]};
    border-radius: 10px;
    padding: 14px 18px 12px 18px;
    box-shadow: 0 1px 2px rgba(15,23,42,0.04);
}}
[data-testid="stMetricValue"] {{font-size: 1.5rem !important; font-weight: 700; color: {PALETTE["text"]};}}
[data-testid="stMetricLabel"] {{font-size: 0.78rem !important; color: {PALETTE["text_muted"]}; font-weight: 500; text-transform: uppercase; letter-spacing: 0.04em;}}
[data-testid="stMetricDelta"] {{font-size: 0.85rem !important; font-weight: 600;}}

/* --- Sidebar --- */
section[data-testid="stSidebar"] {{
    background: {PALETTE["subtle"]};
    border-right: 1px solid {PALETTE["border"]};
}}
section[data-testid="stSidebar"] h3 {{font-size: 1rem; margin-top: 0.5rem;}}

/* --- Cabecera principal --- */
.main-header {{
    border-bottom: 2px solid {PALETTE["border"]};
    padding-bottom: 0.8rem;
    margin-bottom: 1.2rem;
}}
.main-header-title {{
    font-size: 1.6rem;
    font-weight: 700;
    color: {PALETTE["text"]};
    margin: 0;
    line-height: 1.2;
}}
.main-header-subtitle {{
    font-size: 0.85rem;
    color: {PALETTE["text_muted"]};
    margin: 0.15rem 0 0 0;
}}

/* --- Tarjeta de contexto del escenario activo (parte superior de cada pestaña) --- */
.scenario-card {{
    background: linear-gradient(135deg, #EFF6FF 0%, #FFFFFF 100%);
    border: 1px solid #BFDBFE;
    border-left: 4px solid {PALETTE["scenario"]};
    border-radius: 10px;
    padding: 14px 18px;
    margin: 0.6rem 0 1.2rem 0;
    box-shadow: 0 1px 2px rgba(15,23,42,0.03);
}}
.scenario-card-label {{
    font-size: 0.7rem;
    font-weight: 600;
    color: {PALETTE["text_muted"]};
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 4px;
}}
.scenario-card-title {{
    font-size: 1.05rem;
    font-weight: 650;
    color: {PALETTE["text"]};
    margin-bottom: 6px;
}}
.scenario-card-desc {{
    font-size: 0.88rem;
    color: {PALETTE["text"]};
    line-height: 1.45;
    margin: 0;
}}

/* --- Pestañas más prominentes --- */
.stTabs [data-baseweb="tab-list"] {{gap: 4px; border-bottom: 1px solid {PALETTE["border"]};}}
.stTabs [data-baseweb="tab"] {{
    height: 42px;
    padding: 0 18px;
    font-weight: 500;
    color: {PALETTE["text_muted"]};
    background: transparent;
    border-radius: 8px 8px 0 0;
}}
.stTabs [data-baseweb="tab"][aria-selected="true"] {{
    color: {PALETTE["scenario"]};
    font-weight: 650;
    border-bottom: 2px solid {PALETTE["scenario"]};
    background: white;
}}

/* --- Section headers dentro de tabs --- */
.section-title {{
    font-size: 1rem;
    font-weight: 650;
    color: {PALETTE["text"]};
    margin: 0.4rem 0 0.5rem 0;
}}

/* --- Pequeñas mejoras --- */
hr {{margin: 0.6rem 0 1rem 0; border-color: {PALETTE["border"]};}}
small {{color: {PALETTE["text_muted"]};}}
.stExpander {{border-radius: 10px; border-color: {PALETTE["border"]};}}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ============================================================================
# Agrupación de los 200 sectores EXIOBASE en familias
# ============================================================================

SECTOR_GROUPS_KEYWORDS = {
    "🌾 Agricultura, ganadería y pesca": [
        "paddy rice", "wheat", "cereal", "vegetables", "fruit", "oil seeds",
        "sugar cane", "fibers", "crops nec", "cattle", "pigs", "poultry",
        "meat animals", "animal products", "raw milk", "wool", "manure",
        "fishing", "fish", "forestry", "wood logs", "cork",
    ],
    "⛏️ Minería y extracción": [
        "iron ores", "metal ores", "uranium", "thorium", "ores nec",
        "coal", "lignite", "peat", "crude petroleum", "natural gas",
        "stone", "sand", "clay", "salt and other mining", "fertilizer minerals",
        "anthracite", "bituminous", "coking coal",
    ],
    "🍞 Alimentación y bebidas": [
        "products of meat", "fish products", "vegetable oils", "dairy",
        "products of milling", "sugar", "food products", "beverages",
        "tobacco", "products of meat poultry",
    ],
    "🧵 Textil, papel y madera": [
        "textiles", "wearing apparel", "leather", "wood", "pulp", "paper",
        "publishing", "printing",
    ],
    "🧪 Productos químicos y plásticos": [
        "chemicals", "fertilizers", "plastics", "rubber",
    ],
    "⛽ Refino y coque": [
        "coke", "refinery", "petroleum products", "nuclear fuel",
        "hydrocarbons",
    ],
    "🔩 Metales primarios": [
        "basic iron and steel", "primary aluminium", "primary copper",
        "primary lead", "primary zinc", "primary tin", "primary nickel",
        "precious metals", "non-ferrous metals", "foundry",
    ],
    "♻️ Reciclaje y materiales secundarios": [
        "secondary", "re-processing", "treatment, re-processing",
        "treatment of waste",
    ],
    "🏭 Maquinaria y electrónica": [
        "machinery", "office machinery", "computers", "electrical machinery",
        "radio, television", "medical, precision",
    ],
    "🚗 Vehículos y equipo de transporte": [
        "motor vehicles", "trailers", "ships", "boats", "aircraft",
        "railroad", "transport equipment",
    ],
    "🏗️ Construcción": ["construction"],
    "💡 Energía y suministros": [
        "electricity by", "gas distribution", "water collection", "steam",
        "hot water supply",
    ],
    "🛒 Comercio y transporte": [
        "wholesale", "retail trade", "trade services", "transport",
        "transportation services", "supporting and auxiliary",
        "post and telecommunications",
    ],
    "🏥 Servicios públicos": [
        "education", "health", "social work", "public administration",
        "defence",
    ],
    "💼 Otros servicios": [
        "financial intermediation", "insurance", "real estate", "renting of",
        "computer services", "research and development", "business services",
        "membership organisations", "recreational", "cultural", "sporting",
        "personal services", "domestic services", "extra-territorial",
    ],
}


@st.cache_data
def classify_sector(name: str) -> str:
    name_l = str(name).lower()
    for group, keywords in SECTOR_GROUPS_KEYWORDS.items():
        for kw in keywords:
            if kw in name_l:
                return group
    return "📦 Otros"


# ============================================================================
# Helpers de formato y datos
# ============================================================================

@st.cache_data(show_spinner="Cargando datos…")
def get_bundle() -> DataBundle:
    return load_all(prefer="auto")


def get_indicator_meta(bundle: DataBundle, indicator_id: str) -> dict:
    for ind in bundle.metadata["indicators"]:
        if ind["id"] == indicator_id:
            return ind
    return {"id": indicator_id, "label": indicator_id, "unit": "", "kind": "econ"}


def format_value(val: float | None, unit: str) -> str:
    if val is None or pd.isna(val):
        return "—"
    abs_v = abs(val)
    if abs_v >= 1e12: return f"{val/1e12:.2f} T {unit}".strip()
    if abs_v >= 1e9:  return f"{val/1e9:.2f} B {unit}".strip()
    if abs_v >= 1e6:  return f"{val/1e6:.2f} M {unit}".strip()
    if abs_v >= 1e3:  return f"{val/1e3:.2f} k {unit}".strip()
    return f"{val:.2f} {unit}".strip()


def truncate(s: str, n: int = 38) -> str:
    s = str(s)
    return s if len(s) <= n else s[:n-1] + "…"


def add_sector_group_col(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["sector_group"] = df["sector"].apply(classify_sector)
    return df


# Estilos comunes para todos los gráficos plotly
PLOTLY_LAYOUT_DEFAULTS = dict(
    plot_bgcolor="white",
    paper_bgcolor="white",
    font=dict(family="Inter, -apple-system, sans-serif", size=12, color=PALETTE["text"]),
    xaxis=dict(gridcolor=PALETTE["border"], zerolinecolor=PALETTE["border"]),
    yaxis=dict(gridcolor=PALETTE["border"], zerolinecolor=PALETTE["border"]),
    hoverlabel=dict(bgcolor="white", bordercolor=PALETTE["border"],
                    font=dict(family="Inter", size=12)),
)


def apply_plotly_style(fig, **overrides) -> go.Figure:
    """Aplica el estilo común; permite sobrescribir parámetros concretos."""
    layout = {**PLOTLY_LAYOUT_DEFAULTS, **overrides}
    fig.update_layout(**layout)
    return fig


# ============================================================================
# Componente reutilizable: tarjeta de contexto del escenario
# ============================================================================

def render_scenario_card(ctx: dict, *, region_label: str | None = None) -> None:
    sc = ctx["scenario_meta"]
    region_text = (
        f" · Región: <b>{region_label}</b>"
        if region_label and region_label != "(todas)" else
        " · Agregado mundial"
    )
    granularity = "familias sectoriales" if ctx["use_groups"] else "sectores individuales"
    st.markdown(
        f"""
        <div class="scenario-card">
            <div class="scenario-card-label">Escenario activo</div>
            <div class="scenario-card-title">{sc['label']}</div>
            <div class="scenario-card-desc">{sc['description']}</div>
            <div style="margin-top: 8px; font-size: 0.78rem; color: {PALETTE["text_muted"]};">
                Comparación frente al baseline{region_text} · Vista por {granularity}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================================
# Sidebar
# ============================================================================

def render_sidebar(bundle: DataBundle) -> dict:
    md = bundle.metadata

    st.sidebar.markdown("### ♻️ Configuración")

    src_label = "Datos pycirk + EXIOBASE 3.3" if bundle.source == "pycirk" else "Datos sintéticos"
    src_color = PALETTE["positive"] if bundle.source == "pycirk" else PALETTE["accent"]
    st.sidebar.markdown(
        f"<div style='font-size:0.8rem;color:{PALETTE['text_muted']}'>"
        f"<span style='color:{src_color};font-weight:600'>● {src_label}</span><br>"
        f"{len(bundle.df):,} filas · {len(md['regions'])} regiones · "
        f"{len(md['sectors'])} sectores"
        f"</div>",
        unsafe_allow_html=True,
    )
    st.sidebar.divider()

    # Escenario
    st.sidebar.markdown("**🎯 Escenario activo**")
    scenario_options = [s for s in md["scenarios"] if s["id"] != "baseline"]
    scenario_labels = {s["id"]: s["label"] for s in scenario_options}
    scenario_id = st.sidebar.selectbox(
        "scenario", options=[s["id"] for s in scenario_options],
        format_func=lambda x: scenario_labels[x],
        label_visibility="collapsed",
    )
    sc_meta = next(s for s in scenario_options if s["id"] == scenario_id)
    st.sidebar.caption(f"_{sc_meta['description']}_")

    st.sidebar.divider()

    # Filtros
    st.sidebar.markdown("**🔍 Filtros**")
    regions = ["(todas)"] + md["regions"]
    region_choice = st.sidebar.selectbox("Región", regions, index=0)
    region = None if region_choice == "(todas)" else region_choice

    granularity = st.sidebar.radio(
        "Nivel de detalle",
        options=["Familias sectoriales", "Sectores individuales"],
        index=0,
        help="Familias agrupa los 200 productos de EXIOBASE en ~15 categorías "
             "(recomendado para navegación rápida).",
    )
    use_groups = granularity == "Familias sectoriales"

    top_n = st.sidebar.slider(
        "Sectores a mostrar (top-N)", min_value=5, max_value=30, value=12, step=1,
        help="Número de sectores que aparecen en los rankings.",
    )

    return {
        "scenario": scenario_id,
        "region": region,
        "scenario_meta": sc_meta,
        "use_groups": use_groups,
        "top_n": top_n,
    }


# ============================================================================
# Pestaña: Resumen
# ============================================================================

MAIN_INDICATORS = ("value_added", "employment", "co2eq", "energy")


def render_summary_tab(bundle: DataBundle, ctx: dict) -> None:
    df = filter_data(bundle.df, region=ctx["region"])
    sc_id = ctx["scenario"]
    by_col = "sector_group" if ctx["use_groups"] else "sector"
    if ctx["use_groups"]:
        df = add_sector_group_col(df)

    render_scenario_card(ctx, region_label=ctx["region"] or "(todas)")

    # KPIs
    st.markdown('<div class="section-title">Indicadores principales</div>', unsafe_allow_html=True)
    inds_meta = [i for i in bundle.metadata["indicators"] if i["id"] in MAIN_INDICATORS]
    cols = st.columns(len(inds_meta))
    for col, ind in zip(cols, inds_meta):
        val = total_indicator(df, ind["id"], sc_id)
        d_abs, d_rel = delta_vs_baseline(df, ind["id"], sc_id)
        col.metric(
            label=ind["label"],
            value=format_value(val, ind["unit"]),
            delta=f"{d_rel*100:+.2f} %",
            help=f"Δ absoluto: {format_value(d_abs, ind['unit'])}",
        )

    st.divider()

    # Top winners y losers
    cmp = comparison_breakdown(df, "value_added", sc_id, by=by_col)
    cmp = cmp[cmp["baseline"] > 0]
    top_n = ctx["top_n"]

    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown('<div class="section-title">🟢 Sectores con mayor crecimiento</div>',
                    unsafe_allow_html=True)
        winners = cmp[cmp["delta_rel"] > 0].nlargest(top_n, "delta_rel")
        if len(winners):
            fig = go.Figure()
            fig.add_bar(
                y=[truncate(s, 34) for s in winners[by_col]],
                x=winners["delta_rel"] * 100,
                orientation="h",
                marker=dict(color=PALETTE["positive"], line=dict(width=0)),
                hovertext=winners[by_col],
                hovertemplate="<b>%{hovertext}</b><br>Δ %{x:+.2f} %<extra></extra>",
                text=[f"+{v*100:.1f}%" for v in winners["delta_rel"]],
                textposition="outside",
                textfont=dict(size=11, color=PALETTE["text"]),
                cliponaxis=False,
            )
            apply_plotly_style(
                fig,
                height=max(280, 30 * len(winners)),
                margin=dict(l=10, r=110, t=10, b=20),
                xaxis=dict(title="Δ Valor Añadido (%)", gridcolor=PALETTE["border"]),
                yaxis=dict(autorange="reversed", showgrid=False),
            )
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("Sin sectores con crecimiento positivo en este escenario.")

    with col_right:
        st.markdown('<div class="section-title">🔴 Sectores con mayor reducción</div>',
                    unsafe_allow_html=True)
        losers = cmp[cmp["delta_rel"] < 0].nsmallest(top_n, "delta_rel")
        if len(losers):
            fig = go.Figure()
            fig.add_bar(
                y=[truncate(s, 34) for s in losers[by_col]],
                x=losers["delta_rel"] * 100,
                orientation="h",
                marker=dict(color=PALETTE["negative"], line=dict(width=0)),
                hovertext=losers[by_col],
                hovertemplate="<b>%{hovertext}</b><br>Δ %{x:+.2f} %<extra></extra>",
                text=[f"{v*100:.1f}%" for v in losers["delta_rel"]],
                textposition="outside",
                textfont=dict(size=11, color=PALETTE["text"]),
                cliponaxis=False,
            )
            apply_plotly_style(
                fig,
                height=max(280, 30 * len(losers)),
                margin=dict(l=10, r=110, t=10, b=20),
                xaxis=dict(title="Δ Valor Añadido (%)", gridcolor=PALETTE["border"]),
                yaxis=dict(autorange="reversed", showgrid=False),
            )
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("Sin sectores con reducción en este escenario.")

    # Variación por región
    st.divider()
    st.markdown('<div class="section-title">🌍 Variación por región</div>', unsafe_allow_html=True)
    region_cols = st.columns(len(inds_meta))
    for idx, ind in enumerate(inds_meta):
        with region_cols[idx]:
            st.markdown(f"<small><b>{ind['label']}</b></small>", unsafe_allow_html=True)
            for region_name in bundle.metadata["regions"]:
                base_v = df[(df["scenario"] == "baseline") &
                            (df["region"] == region_name) &
                            (df["indicator"] == ind["id"])]["value"].sum()
                sc_v = df[(df["scenario"] == sc_id) &
                          (df["region"] == region_name) &
                          (df["indicator"] == ind["id"])]["value"].sum()
                if base_v == 0:
                    continue
                delta_pct = (sc_v - base_v) / base_v * 100
                arrow = "↑" if delta_pct >= 0 else "↓"
                color = PALETTE["positive"] if delta_pct >= 0 else PALETTE["negative"]
                st.markdown(
                    f"<small>{region_name}</small> "
                    f"<span style='color:{color};font-weight:600'>"
                    f"{arrow} {delta_pct:+.2f} %</span>",
                    unsafe_allow_html=True,
                )


# ============================================================================
# Pestaña: Económico
# ============================================================================

def render_econ_tab(bundle: DataBundle, ctx: dict) -> None:
    df = filter_data(bundle.df, region=ctx["region"])
    sc_id = ctx["scenario"]
    by_col = "sector_group" if ctx["use_groups"] else "sector"
    if ctx["use_groups"]:
        df = add_sector_group_col(df)

    render_scenario_card(ctx, region_label=ctx["region"] or "(todas)")

    indicator = st.selectbox(
        "Indicador económico",
        options=["value_added", "employment", "output"],
        format_func=lambda i: get_indicator_meta(bundle, i)["label"],
        key="econ_ind",
    )
    ind_meta = get_indicator_meta(bundle, indicator)

    val = total_indicator(df, indicator, sc_id)
    d_abs, d_rel = delta_vs_baseline(df, indicator, sc_id)
    base_v = total_indicator(df, indicator, "baseline")

    cols = st.columns(3)
    cols[0].metric("Baseline", format_value(base_v, ind_meta["unit"]))
    cols[1].metric("Escenario", format_value(val, ind_meta["unit"]),
                   delta=f"{d_rel*100:+.2f} %")
    cols[2].metric("Δ absoluta", format_value(d_abs, ind_meta["unit"]))

    st.divider()

    cmp = comparison_breakdown(df, indicator, sc_id, by=by_col)
    cmp = cmp[cmp["baseline"] > 0]

    if ctx["use_groups"]:
        cmp_sorted = cmp.sort_values("baseline", ascending=False)
        st.markdown('<div class="section-title">Comparación por familia sectorial</div>',
                    unsafe_allow_html=True)
        labels = [truncate(s, 34) for s in cmp_sorted[by_col]]
        fig = go.Figure()
        fig.add_bar(name="Baseline", x=labels, y=cmp_sorted["baseline"],
                    marker=dict(color=PALETTE["baseline"], line=dict(width=0)),
                    hovertext=cmp_sorted[by_col],
                    hovertemplate="<b>%{hovertext}</b><br>Baseline: %{y:,.0f}<extra></extra>")
        fig.add_bar(name="Escenario", x=labels, y=cmp_sorted["scenario"],
                    marker=dict(color=PALETTE["scenario"], line=dict(width=0)),
                    hovertext=cmp_sorted[by_col],
                    hovertemplate="<b>%{hovertext}</b><br>Escenario: %{y:,.0f}<extra></extra>")
        apply_plotly_style(
            fig,
            barmode="group", height=460,
            margin=dict(l=10, r=10, t=10, b=180),
            xaxis=dict(tickangle=-30),
            yaxis=dict(title=f"{ind_meta['label']} ({ind_meta['unit']})"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                        bgcolor="rgba(255,255,255,0.9)"),
        )
        st.plotly_chart(fig, width="stretch")
    else:
        top_n = ctx["top_n"]
        cmp_top = cmp.iloc[cmp["delta_abs"].abs().argsort()[::-1]].head(top_n)
        st.markdown(f'<div class="section-title">Top {top_n} sectores por |Δ absoluta|</div>',
                    unsafe_allow_html=True)
        labels = [truncate(s, 38) for s in cmp_top[by_col]]
        fig = go.Figure()
        fig.add_bar(name="Baseline", x=labels, y=cmp_top["baseline"],
                    marker=dict(color=PALETTE["baseline"], line=dict(width=0)),
                    hovertext=cmp_top[by_col],
                    hovertemplate="<b>%{hovertext}</b><br>Baseline: %{y:,.0f}<extra></extra>")
        fig.add_bar(name="Escenario", x=labels, y=cmp_top["scenario"],
                    marker=dict(color=PALETTE["scenario"], line=dict(width=0)),
                    hovertext=cmp_top[by_col],
                    hovertemplate="<b>%{hovertext}</b><br>Escenario: %{y:,.0f}<extra></extra>")
        apply_plotly_style(
            fig,
            barmode="group", height=470,
            margin=dict(l=10, r=10, t=10, b=220),
            xaxis=dict(tickangle=-32),
            yaxis=dict(title=f"{ind_meta['label']} ({ind_meta['unit']})"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                        bgcolor="rgba(255,255,255,0.9)"),
        )
        st.plotly_chart(fig, width="stretch")
        st.caption(
            f"Mostrando los {top_n} sectores con mayor variación absoluta. "
            "Cambia a «Familias sectoriales» en la barra lateral para ver los 15 grupos completos."
        )

    with st.expander("📋 Tabla detallada (con búsqueda y descarga)", expanded=False):
        table = cmp.copy()
        table["delta_rel"] = (table["delta_rel"] * 100).round(2)
        table["delta_abs"] = table["delta_abs"].round(0)
        table["baseline"] = table["baseline"].round(0)
        table["scenario"] = table["scenario"].round(0)
        col_label = "Familia sectorial" if ctx["use_groups"] else "Sector"
        table.columns = [col_label, "Baseline", "Escenario", "Δ absoluta", "Δ relativa (%)"]
        table = table.sort_values("Δ relativa (%)", key=lambda s: s.abs(), ascending=False)
        st.dataframe(table, width="stretch", hide_index=True)
        csv = table.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📥 Descargar tabla (CSV)", csv,
            file_name=f"{sc_id}_{indicator}_economico.csv", mime="text/csv",
        )


# ============================================================================
# Pestaña: Ambiental
# ============================================================================

def render_env_tab(bundle: DataBundle, ctx: dict) -> None:
    df = filter_data(bundle.df, region=ctx["region"])
    sc_id = ctx["scenario"]
    by_col = "sector_group" if ctx["use_groups"] else "sector"
    if ctx["use_groups"]:
        df = add_sector_group_col(df)

    render_scenario_card(ctx, region_label=ctx["region"] or "(todas)")

    indicator = st.selectbox(
        "Indicador ambiental",
        options=["co2eq", "energy", "materials", "land_use"],
        format_func=lambda i: get_indicator_meta(bundle, i)["label"],
        key="env_ind",
    )
    ind_meta = get_indicator_meta(bundle, indicator)

    val = total_indicator(df, indicator, sc_id)
    d_abs, d_rel = delta_vs_baseline(df, indicator, sc_id)
    base_v = total_indicator(df, indicator, "baseline")

    cols = st.columns(3)
    cols[0].metric("Baseline", format_value(base_v, ind_meta["unit"]))
    cols[1].metric("Escenario", format_value(val, ind_meta["unit"]),
                   delta=f"{d_rel*100:+.2f} %")
    cols[2].metric("Δ absoluta", format_value(d_abs, ind_meta["unit"]))

    st.divider()

    col_left, col_right = st.columns([1, 1.4])

    with col_left:
        st.markdown('<div class="section-title">Por región</div>', unsafe_allow_html=True)
        region_rows = []
        for r in bundle.metadata["regions"]:
            base = df[(df["region"] == r) & (df["scenario"] == "baseline") &
                      (df["indicator"] == indicator)]["value"].sum()
            sc = df[(df["region"] == r) & (df["scenario"] == sc_id) &
                    (df["indicator"] == indicator)]["value"].sum()
            region_rows.append({"region": r, "baseline": base, "scenario": sc,
                                "delta_pct": (sc - base) / base * 100 if base else 0})
        region_df = pd.DataFrame(region_rows)
        fig = go.Figure()
        fig.add_bar(name="Baseline", x=region_df["region"], y=region_df["baseline"],
                    marker=dict(color=PALETTE["baseline"], line=dict(width=0)))
        fig.add_bar(name="Escenario", x=region_df["region"], y=region_df["scenario"],
                    marker=dict(color=PALETTE["scenario"], line=dict(width=0)),
                    text=[f"{v:+.1f} %" for v in region_df["delta_pct"]],
                    textposition="outside",
                    textfont=dict(size=11),
                    cliponaxis=False)
        apply_plotly_style(
            fig,
            barmode="group", height=380,
            margin=dict(l=10, r=10, t=30, b=10),
            yaxis=dict(title=f"{ind_meta['label']} ({ind_meta['unit']})"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                        bgcolor="rgba(255,255,255,0.9)"),
        )
        st.plotly_chart(fig, width="stretch")

    with col_right:
        st.markdown('<div class="section-title">Sectores que más mueven el indicador</div>',
                    unsafe_allow_html=True)
        top = important_sectors(
            df.assign(sector=df[by_col]) if ctx["use_groups"] else df,
            indicator, sc_id, n=ctx["top_n"]
        )
        # Verde si reduce impacto ambiental, rojo si lo aumenta
        colors = [PALETTE["positive"] if v < 0 else PALETTE["negative"] for v in top["delta_abs"]]
        fig = go.Figure()
        fig.add_bar(
            x=top["delta_abs"], y=[truncate(s, 34) for s in top["sector"]],
            orientation="h",
            marker=dict(color=colors, line=dict(width=0)),
            hovertext=top["sector"],
            hovertemplate="<b>%{hovertext}</b><br>Δ %{x:+,.2f}<extra></extra>",
            text=[format_value(v, ind_meta["unit"]) for v in top["delta_abs"]],
            textposition="outside",
            textfont=dict(size=11, color=PALETTE["text"]),
            cliponaxis=False,
        )
        apply_plotly_style(
            fig,
            height=max(380, 30 * len(top)),
            margin=dict(l=10, r=140, t=10, b=10),
            xaxis=dict(title=f"Δ {ind_meta['label']}"),
            yaxis=dict(autorange="reversed", showgrid=False),
        )
        st.plotly_chart(fig, width="stretch")

    with st.expander("📋 Tabla detallada", expanded=False):
        cmp = comparison_breakdown(df, indicator, sc_id, by=by_col)
        cmp = cmp[cmp["baseline"] > 0]
        col_label = "Familia sectorial" if ctx["use_groups"] else "Sector"
        table = cmp.copy()
        table["delta_rel"] = (table["delta_rel"] * 100).round(2)
        table.columns = [col_label, "Baseline", "Escenario", "Δ absoluta", "Δ relativa (%)"]
        table = table.sort_values("Δ relativa (%)", key=lambda s: s.abs(), ascending=False)
        st.dataframe(table, width="stretch", hide_index=True)
        csv = table.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Descargar tabla (CSV)", csv,
                           file_name=f"{sc_id}_{indicator}_ambiental.csv", mime="text/csv")


# ============================================================================
# Pestaña: Sensibilidad
# ============================================================================

def render_sensitivity_tab(bundle: DataBundle, ctx: dict) -> None:
    df = filter_data(bundle.df, region=ctx["region"])
    sc_id = ctx["scenario"]
    by_col = "sector_group" if ctx["use_groups"] else "sector"
    if ctx["use_groups"]:
        df = add_sector_group_col(df)

    render_scenario_card(ctx, region_label=ctx["region"] or "(todas)")

    st.caption(
        "Identifica los sectores con mayor poder explicativo sobre los resultados, siguiendo la lógica "
        "de identificación de coeficientes importantes (Miller & Blair, 2009, cap. 12)."
    )

    indicator = st.selectbox(
        "Indicador objetivo",
        options=["value_added", "employment", "co2eq", "energy"],
        format_func=lambda i: get_indicator_meta(bundle, i)["label"],
        key="sens_ind",
    )
    ind_meta = get_indicator_meta(bundle, indicator)

    granularity_label = "familia" if ctx["use_groups"] else "sector"
    st.markdown(
        f'<div class="section-title">Tornado plot — variación relativa por {granularity_label}</div>',
        unsafe_allow_html=True,
    )
    tornado = tornado_data(
        df.assign(sector=df[by_col]) if ctx["use_groups"] else df,
        indicator, sc_id, top_n=ctx["top_n"], by="sector",
    )
    # Posicionar los textos dentro de la barra cuando es positivo y outside cuando es negativo
    text_positions = ["outside" if v >= 0 else "outside" for v in tornado["delta_rel"]]
    fig = go.Figure()
    fig.add_bar(
        x=tornado["delta_rel"] * 100,
        y=[truncate(s, 36) for s in tornado["sector"]],
        orientation="h",
        marker=dict(
            color=[PALETTE["positive"] if v >= 0 else PALETTE["negative"]
                   for v in tornado["delta_rel"]],
            line=dict(width=0),
        ),
        hovertext=tornado["sector"],
        hovertemplate="<b>%{hovertext}</b><br>Δ %{x:+.2f} %<extra></extra>",
        text=[f"{v*100:+.2f} %" for v in tornado["delta_rel"]],
        textposition=text_positions,
        textfont=dict(size=11, color=PALETTE["text"]),
        cliponaxis=False,
    )
    apply_plotly_style(
        fig,
        height=max(380, 32 * len(tornado)),
        margin=dict(l=10, r=120, t=10, b=10),
        xaxis=dict(title=f"Δ {ind_meta['label']} (%) respecto al baseline",
                   zeroline=True, zerolinewidth=1, zerolinecolor=PALETTE["text_muted"]),
        yaxis=dict(autorange="reversed", showgrid=False),
    )
    st.plotly_chart(fig, width="stretch")

    with st.expander("📐 Elasticidades sectoriales (avanzado)", expanded=False):
        st.caption(
            "ε = Δlog(indicador agregado) / Δlog(producción del sector). "
            "Valores próximos a cero indican baja sensibilidad."
        )
        if not ctx["use_groups"]:
            sectors = bundle.metadata["sectors"]
            inds = ["value_added", "employment", "co2eq", "energy"]
            elasticities = elasticity_table(df, inds, sectors, sc_id)
            pretty = elasticities.copy()
            for c in inds:
                pretty[c] = pretty[c].round(3)
            rename = {i: get_indicator_meta(bundle, i)["label"] for i in inds}
            pretty = pretty.rename(columns={"sector": "Sector", **rename})
            pretty = pretty.iloc[
                pretty[get_indicator_meta(bundle, "value_added")["label"]].abs().argsort()[::-1]
            ].head(50)
            st.dataframe(pretty, width="stretch", hide_index=True)
        else:
            st.info("Cambia a «Sectores individuales» en la barra lateral para ver elasticidades.")


# ============================================================================
# Pestaña: Acerca de
# ============================================================================

def render_about_tab(bundle: DataBundle) -> None:
    md = bundle.metadata
    src = bundle.source

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("### Estado del dataset")
        st.markdown(f"- **Fuente activa:** `{src}`")
        st.markdown(f"- **Filas:** {len(bundle.df):,}")
        st.markdown(f"- **Regiones:** {len(md['regions'])} ({', '.join(md['regions'])})")
        st.markdown(f"- **Sectores individuales:** {len(md['sectors'])}")
        st.markdown(f"- **Familias agregadas:** {len(SECTOR_GROUPS_KEYWORDS)}")
        st.markdown(f"- **Indicadores:** {len(md['indicators'])}")
        st.markdown(f"- **Escenarios:** {len(md['scenarios'])}")
    with col_b:
        st.markdown("### Arquitectura")
        st.markdown(
            "- `dashboard/data_loader.py` — capa de acceso a datos\n"
            "- `dashboard/sensitivity.py` — análisis de sensibilidad y elasticidades\n"
            "- `dashboard/app.py` — interfaz Streamlit (este archivo)\n"
            "- `scripts/generate_synthetic_data.py` — generador sintético\n"
            "- `scripts/run_pycirk.py` — orquestador pycirk\n"
            "- `scripts/convert_pycirk_output.py` — converter pycirk → esquema canónico\n"
            "- `scripts/build_circular_scenarios.py` — generador de scenarios.xlsx"
        )

    st.divider()
    st.markdown("### Sobre el TFG")
    st.markdown(
        """
        Esta aplicación es el componente software del Trabajo de Fin de Grado *«Desarrollo de un
        Dashboard Interactivo para la Simulación de Escenarios de Economía Circular»* (Universidad
        San Pablo-CEU, curso 2025/2026). Combina el motor científico **pycirk** (Donati et al., 2020)
        sobre la base de datos **EXIOBASE 3.3.sm** (Stadler et al., 2018) con una capa de visualización
        moderna en Streamlit.

        **Referencias clave**: Donati et al. (2020, 2021), Stadler et al. (2018),
        Geissdoerfer et al. (2017), Miller & Blair (2009).

        **Repositorio**: [github.com/javidrb/tfg-circular-dashboard](https://github.com/javidrb/tfg-circular-dashboard)
        """
    )


# ============================================================================
# Entry point
# ============================================================================

def main() -> None:
    bundle = get_bundle()

    st.markdown(
        f"""
        <div class="main-header">
            <h1 class="main-header-title">♻️ Dashboard de escenarios de economía circular</h1>
            <p class="main-header-subtitle">
                TFG · Javier de Ramón Boj · Universidad San Pablo-CEU · curso 2025/2026 ·
                <a href="https://github.com/javidrb/tfg-circular-dashboard" target="_blank"
                   style="color: {PALETTE['scenario']}; text-decoration: none;">repositorio</a>
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    ctx = render_sidebar(bundle)

    tabs = st.tabs(["📊 Resumen", "💶 Económico", "🌍 Ambiental", "🎯 Sensibilidad", "ℹ️ Acerca de"])
    with tabs[0]: render_summary_tab(bundle, ctx)
    with tabs[1]: render_econ_tab(bundle, ctx)
    with tabs[2]: render_env_tab(bundle, ctx)
    with tabs[3]: render_sensitivity_tab(bundle, ctx)
    with tabs[4]: render_about_tab(bundle)


if __name__ == "__main__":
    main()
