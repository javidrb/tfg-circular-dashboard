"""
Dashboard interactivo para la simulación de escenarios de economía circular.

Lanzamiento:
    streamlit run dashboard/app.py

La app lee `data/synthetic/all_scenarios.parquet` (o `data/pycirk_runs/...`
cuando esté disponible) a través de `dashboard.data_loader`. Toda la lógica
de cálculo está fuera de este archivo: aquí sólo hay UI.
"""
from __future__ import annotations

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
    sector_breakdown,
    total_indicator,
)
from dashboard.sensitivity import elasticity_table, important_sectors, tornado_data

# --------------------------------------------------------------------------- #
# Configuración general
# --------------------------------------------------------------------------- #

st.set_page_config(
    page_title="Dashboard Economía Circular | TFG",
    page_icon="♻️",
    layout="wide",
    initial_sidebar_state="expanded",
)

PALETTE = {
    "baseline": "#7F7F7F",
    "scenario": "#1F77B4",
    "positive": "#2CA02C",
    "negative": "#D62728",
    "neutral":  "#9C9C9C",
}

INDICATOR_KIND_LABEL = {"econ": "Económicos", "env": "Ambientales"}


# --------------------------------------------------------------------------- #
# Carga de datos (cacheada)
# --------------------------------------------------------------------------- #

@st.cache_data(show_spinner="Cargando datos…")
def get_bundle() -> DataBundle:
    return load_all(prefer="auto")


def get_indicator_meta(bundle: DataBundle, indicator_id: str) -> dict:
    for ind in bundle.metadata["indicators"]:
        if ind["id"] == indicator_id:
            return ind
    return {"id": indicator_id, "label": indicator_id, "unit": "", "kind": "econ"}


# --------------------------------------------------------------------------- #
# Sidebar: palancas y filtros
# --------------------------------------------------------------------------- #

def render_sidebar(bundle: DataBundle) -> dict:
    md = bundle.metadata
    st.sidebar.title("♻️ Configuración")

    # Fuente de datos
    src_label = "Datos sintéticos (desarrollo)" if bundle.source == "synthetic" else "Datos pycirk"
    st.sidebar.caption(f"Fuente: **{src_label}**")
    st.sidebar.divider()

    # Selección de escenario
    st.sidebar.subheader("Escenario")
    scenario_options = [s for s in md["scenarios"] if s["id"] != "baseline"]
    scenario_labels = {s["id"]: s["label"] for s in scenario_options}
    scenario_id = st.sidebar.selectbox(
        "Escenario activo",
        options=[s["id"] for s in scenario_options],
        format_func=lambda x: scenario_labels[x],
        help="El escenario se compara siempre frente al baseline (sin intervención).",
    )
    sc_meta = next(s for s in scenario_options if s["id"] == scenario_id)
    st.sidebar.caption(sc_meta["description"])

    st.sidebar.divider()

    # Palancas (informativas en MVP — el escenario ya está pre-calculado)
    st.sidebar.subheader("Palancas (lecturas)")
    st.sidebar.caption(
        "En esta versión, los escenarios ya están pre-calculados a partir de pycirk. "
        "Las palancas reflejan los parámetros aplicados; en el siguiente sprint serán editables."
    )
    if "vida_util" in scenario_id:
        st.sidebar.slider("Vida útil vehículos (%)", 0, 60,
                          value=10 if "10" in scenario_id else 50, disabled=True, help="Porcentaje de aumento sobre el baseline.")
    if "acero_secundario" in scenario_id:
        st.sidebar.slider("Acero secundario (%)", 0, 60, value=30, disabled=True)
    if "eficiencia" in scenario_id:
        st.sidebar.slider("Eficiencia energética (%)", 0, 40, value=20, disabled=True)

    st.sidebar.divider()

    # Filtros
    st.sidebar.subheader("Filtros")
    regions = ["(todas)"] + md["regions"]
    region_choice = st.sidebar.selectbox("Región", regions, index=0)
    region = None if region_choice == "(todas)" else region_choice

    return {"scenario": scenario_id, "region": region, "scenario_meta": sc_meta}


# --------------------------------------------------------------------------- #
# Tabs
# --------------------------------------------------------------------------- #

def fmt(val: float, unit: str) -> str:
    if abs(val) >= 1e6:
        return f"{val/1e6:,.2f} M{unit}".replace(",", " ")
    if abs(val) >= 1e3:
        return f"{val/1e3:,.2f} k{unit}".replace(",", " ")
    return f"{val:,.2f} {unit}".replace(",", " ")


def kpi_box(col, label: str, val: float, delta_abs: float, delta_rel: float, unit: str) -> None:
    col.metric(
        label=label,
        value=fmt(val, unit),
        delta=f"{delta_rel*100:+.2f} %  ({fmt(delta_abs, unit)})",
        delta_color="normal",
    )


def render_summary_tab(bundle: DataBundle, ctx: dict) -> None:
    df = filter_data(bundle.df, region=ctx["region"])
    sc_id = ctx["scenario"]

    st.subheader("Resumen de impacto")
    st.caption(
        f"Comparación **{ctx['scenario_meta']['label']}** vs. baseline."
        + (f" Región: **{ctx['region']}**." if ctx["region"] else " Agregado mundial.")
    )

    main_inds = [i for i in bundle.metadata["indicators"] if i["id"] in
                 ("value_added", "employment", "co2eq", "energy")]
    cols = st.columns(len(main_inds))
    for col, ind in zip(cols, main_inds):
        val = total_indicator(df, ind["id"], sc_id)
        d_abs, d_rel = delta_vs_baseline(df, ind["id"], sc_id)
        kpi_box(col, ind["label"], val, d_abs, d_rel, ind["unit"])

    st.divider()

    # Gráfico de barras comparativo (totales por escenario, top sectores)
    st.markdown("##### Sectores más afectados (variación relativa)")
    cmp = comparison_breakdown(df, "value_added", sc_id, by="sector")
    cmp = cmp.iloc[cmp["delta_rel"].abs().argsort()[::-1]].head(10)
    fig = go.Figure()
    fig.add_bar(
        y=cmp["sector"], x=cmp["delta_rel"]*100, orientation="h",
        marker_color=[PALETTE["positive"] if v >= 0 else PALETTE["negative"] for v in cmp["delta_rel"]],
        text=[f"{v*100:+.2f} %" for v in cmp["delta_rel"]],
        textposition="outside",
    )
    fig.update_layout(
        height=380, margin=dict(l=10, r=20, t=20, b=20),
        xaxis_title="Δ Valor Añadido (%)", yaxis=dict(autorange="reversed"),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_econ_tab(bundle: DataBundle, ctx: dict) -> None:
    df = filter_data(bundle.df, region=ctx["region"])
    sc_id = ctx["scenario"]

    st.subheader("Indicadores económicos")

    indicator = st.selectbox(
        "Indicador",
        options=["value_added", "employment", "output"],
        format_func=lambda i: get_indicator_meta(bundle, i)["label"],
    )
    ind_meta = get_indicator_meta(bundle, indicator)

    # Comparativa por sector
    cmp = comparison_breakdown(df, indicator, sc_id, by="sector")
    fig = go.Figure()
    fig.add_bar(name="Baseline", x=cmp["sector"], y=cmp["baseline"], marker_color=PALETTE["baseline"])
    fig.add_bar(name="Escenario", x=cmp["sector"], y=cmp["scenario"], marker_color=PALETTE["scenario"])
    fig.update_layout(
        barmode="group", height=420,
        margin=dict(l=10, r=10, t=20, b=120),
        xaxis_tickangle=-35,
        yaxis_title=f"{ind_meta['label']} ({ind_meta['unit']})",
    )
    st.plotly_chart(fig, use_container_width=True)

    # Tabla detallada
    st.markdown("##### Tabla por sector")
    table = cmp.copy()
    table["delta_rel"] = (table["delta_rel"]*100).round(2)
    table["delta_abs"] = table["delta_abs"].round(0)
    table["baseline"] = table["baseline"].round(0)
    table["scenario"] = table["scenario"].round(0)
    table.columns = ["Sector", "Baseline", "Escenario", "Δ absoluta", "Δ relativa (%)"]
    st.dataframe(table, use_container_width=True, hide_index=True)

    csv = table.to_csv(index=False).encode("utf-8")
    st.download_button("📥 Descargar tabla (CSV)", csv,
                       file_name=f"{sc_id}_{indicator}_economico.csv", mime="text/csv")


def render_env_tab(bundle: DataBundle, ctx: dict) -> None:
    df = filter_data(bundle.df, region=ctx["region"])
    sc_id = ctx["scenario"]

    st.subheader("Indicadores ambientales")

    indicator = st.selectbox(
        "Indicador",
        options=["co2eq", "materials", "energy"],
        format_func=lambda i: get_indicator_meta(bundle, i)["label"],
    )
    ind_meta = get_indicator_meta(bundle, indicator)

    col1, col2 = st.columns([2, 3])

    # Mapa de calor por región (heatmap) — comparativa simple
    with col1:
        st.markdown("##### Por región")
        agg = aggregate_indicator(df, indicator, by="region")
        pivot = agg.pivot(index="region", columns="scenario", values="value").fillna(0)
        if "baseline" in pivot.columns and sc_id in pivot.columns:
            pivot["Δ %"] = (pivot[sc_id] - pivot["baseline"]) / pivot["baseline"].replace(0, pd.NA) * 100
            pivot = pivot.sort_values("Δ %", key=lambda s: s.abs(), ascending=False)
        fig = px.bar(
            pivot.reset_index(),
            x="region", y=sc_id, color="Δ %", text=pivot["Δ %"].round(1).astype(str) + " %",
            color_continuous_scale="RdYlGn_r", color_continuous_midpoint=0,
            labels={"region": "Región", sc_id: f"{ind_meta['label']} ({ind_meta['unit']})"},
        )
        fig.update_layout(height=420, margin=dict(l=10, r=10, t=10, b=10),
                          xaxis_tickangle=-35, coloraxis_colorbar_title="Δ %")
        st.plotly_chart(fig, use_container_width=True)

    # Top sectores que más mueven el indicador
    with col2:
        st.markdown("##### Sectores más sensibles")
        top = important_sectors(df, indicator, sc_id, n=10)
        fig = go.Figure()
        fig.add_bar(
            x=top["delta_abs"], y=top["sector"], orientation="h",
            marker_color=[PALETTE["negative"] if v >= 0 else PALETTE["positive"] for v in top["delta_abs"]],
            text=[f"{v:+,.1f} {ind_meta['unit']}" for v in top["delta_abs"]],
            textposition="outside",
        )
        fig.update_layout(
            height=420, margin=dict(l=10, r=20, t=10, b=10),
            xaxis_title=f"Δ {ind_meta['label']} ({ind_meta['unit']})",
            yaxis=dict(autorange="reversed"),
        )
        st.plotly_chart(fig, use_container_width=True)


def render_sensitivity_tab(bundle: DataBundle, ctx: dict) -> None:
    df = filter_data(bundle.df, region=ctx["region"])
    sc_id = ctx["scenario"]

    st.subheader("Análisis de sensibilidad")
    st.caption(
        "Identifica los sectores con mayor poder explicativo sobre los resultados. "
        "Sigue la lógica de identificación de coeficientes importantes "
        "(Miller & Blair, 2009, cap. 12)."
    )

    indicator = st.selectbox(
        "Indicador objetivo",
        options=["value_added", "employment", "co2eq", "energy"],
        format_func=lambda i: get_indicator_meta(bundle, i)["label"],
        key="sens_ind",
    )
    ind_meta = get_indicator_meta(bundle, indicator)

    # Tornado plot
    st.markdown("##### Tornado plot — variación relativa por sector")
    tornado = tornado_data(df, indicator, sc_id, top_n=12, by="sector")
    fig = go.Figure()
    fig.add_bar(
        x=tornado["delta_rel"]*100, y=tornado["sector"], orientation="h",
        marker_color=[PALETTE["positive"] if v >= 0 else PALETTE["negative"] for v in tornado["delta_rel"]],
        text=[f"{v*100:+.2f} %" for v in tornado["delta_rel"]],
        textposition="outside",
    )
    fig.update_layout(
        height=480, margin=dict(l=10, r=30, t=10, b=10),
        xaxis_title=f"Δ {ind_meta['label']} (%) respecto al baseline",
        yaxis=dict(autorange="reversed"),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Tabla de elasticidades agregadas
    st.markdown("##### Elasticidades sectoriales")
    st.caption("ε = Δlog(indicador agregado) / Δlog(producción del sector). "
               "Los valores próximos a cero indican baja sensibilidad.")

    sectors = bundle.metadata["sectors"]
    inds = ["value_added", "employment", "co2eq", "energy"]
    elasticities = elasticity_table(df, inds, sectors, sc_id)
    pretty = elasticities.copy()
    for c in inds:
        pretty[c] = pretty[c].round(3)
    rename = {i: get_indicator_meta(bundle, i)["label"] for i in inds}
    pretty = pretty.rename(columns={"sector": "Sector", **rename})
    st.dataframe(pretty, use_container_width=True, hide_index=True)


def render_about_tab(bundle: DataBundle) -> None:
    st.subheader("Sobre este dashboard")
    md = bundle.metadata
    st.markdown(
        """
Esta aplicación es el MVP del Trabajo de Fin de Grado **«Desarrollo de un dashboard
interactivo para la simulación de escenarios de economía circular»** (Universidad
San Pablo-CEU, curso 2025/2026).

**Estado actual.** Los escenarios se cargan desde datos sintéticos compatibles con
la salida de pycirk + EXIOBASE 3.3.sm. La conexión con el motor real está prevista
para la fase F3 del plan de trabajo.

**Arquitectura.**
- `dashboard/data_loader.py` — capa de acceso a datos.
- `dashboard/sensitivity.py` — análisis de sensibilidad y elasticidades.
- `dashboard/app.py` — interfaz Streamlit (este archivo).
- `scripts/generate_synthetic_data.py` — generador de datos sintéticos.

**Referencias clave.** Donati et al. (2020, 2021), Stadler et al. (2018),
Geissdoerfer et al. (2017), Miller & Blair (2009).
        """
    )

    st.markdown(f"**Fuente activa:** `{bundle.source}`")
    st.markdown(f"**Filas en el dataset:** {len(bundle.df):,}")
    st.markdown(f"**Regiones:** {len(md['regions'])} | **Sectores:** {len(md['sectors'])} | "
                f"**Indicadores:** {len(md['indicators'])} | **Escenarios:** {len(md['scenarios'])}")


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #

def main() -> None:
    bundle = get_bundle()

    st.title("Dashboard de escenarios de economía circular")
    st.caption("TFG · Javier de Ramón Boj · Universidad San Pablo-CEU · 2025/2026")

    ctx = render_sidebar(bundle)

    tabs = st.tabs(["📊 Resumen", "💶 Económico", "🌍 Ambiental", "🎯 Sensibilidad", "ℹ️ Acerca de"])
    with tabs[0]: render_summary_tab(bundle, ctx)
    with tabs[1]: render_econ_tab(bundle, ctx)
    with tabs[2]: render_env_tab(bundle, ctx)
    with tabs[3]: render_sensitivity_tab(bundle, ctx)
    with tabs[4]: render_about_tab(bundle)


if __name__ == "__main__":
    main()
