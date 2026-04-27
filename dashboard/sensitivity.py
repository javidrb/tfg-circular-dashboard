"""
Análisis de sensibilidad y elasticidades sectoriales.

Provee dos utilidades clave:
- `tornado_data`: ordena los sectores por la magnitud del cambio relativo que
  introduce el escenario respecto al baseline para un indicador dado.
- `elasticity_table`: estima la elasticidad del indicador respecto a cambios
  marginales en la producción del sector (∂log V / ∂log x_j).
- `sensitivity_grid`: produce una tabla compacta con las elasticidades de
  cada par (indicador, sector) para un escenario.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


# --------------------------------------------------------------------------- #
# Tornado: rankings de sectores por magnitud del impacto
# --------------------------------------------------------------------------- #

def tornado_data(
    df: pd.DataFrame,
    indicator: str,
    scenario: str,
    *,
    top_n: int = 10,
    by: str = "sector",
) -> pd.DataFrame:
    """
    Devuelve el top-N de sectores (o regiones) ordenados por |Δrel|, listos para
    pintar como tornado plot.

    Salida: columnas [by, baseline, scenario, delta_abs, delta_rel]
    """
    base = df[(df["indicator"] == indicator) & (df["scenario"] == "baseline")]
    sc = df[(df["indicator"] == indicator) & (df["scenario"] == scenario)]

    base_g = base.groupby(by, as_index=False)["value"].sum().rename(columns={"value": "baseline"})
    sc_g = sc.groupby(by, as_index=False)["value"].sum().rename(columns={"value": "scenario"})

    out = base_g.merge(sc_g, on=by, how="outer").fillna(0.0)
    out["delta_abs"] = out["scenario"] - out["baseline"]
    out["delta_rel"] = np.where(out["baseline"] != 0, out["delta_abs"] / out["baseline"], 0.0)

    out = out.iloc[out["delta_rel"].abs().argsort()[::-1]].reset_index(drop=True)
    return out.head(top_n)


# --------------------------------------------------------------------------- #
# Elasticidades sectoriales
# --------------------------------------------------------------------------- #

def elasticity(
    df: pd.DataFrame,
    indicator: str,
    sector: str,
    scenario: str,
) -> float:
    """
    Elasticidad agregada del indicador respecto a la producción del sector,
    estimada a partir del cambio observado entre baseline y escenario:

        ε = Δlog(V) / Δlog(x_j)

    donde V es el indicador agregado y x_j la producción del sector j.
    Devuelve 0.0 si la producción del sector no varía.
    """
    base_v = df[(df["indicator"] == indicator) & (df["scenario"] == "baseline")]["value"].sum()
    sc_v = df[(df["indicator"] == indicator) & (df["scenario"] == scenario)]["value"].sum()

    base_x = df[(df["indicator"] == "output") & (df["scenario"] == "baseline") & (df["sector"] == sector)]["value"].sum()
    sc_x = df[(df["indicator"] == "output") & (df["scenario"] == scenario) & (df["sector"] == sector)]["value"].sum()

    if base_v <= 0 or base_x <= 0 or sc_x <= 0:
        return 0.0
    if abs(sc_x - base_x) / base_x < 1e-9:
        return 0.0

    dlog_v = np.log(sc_v / base_v) if sc_v > 0 else 0.0
    dlog_x = np.log(sc_x / base_x)
    return float(dlog_v / dlog_x) if dlog_x != 0 else 0.0


def elasticity_table(
    df: pd.DataFrame,
    indicators: list[str],
    sectors: list[str],
    scenario: str,
) -> pd.DataFrame:
    """Tabla (sector × indicador) con elasticidades agregadas."""
    rows = []
    for sector in sectors:
        row = {"sector": sector}
        for ind in indicators:
            row[ind] = elasticity(df, ind, sector, scenario)
        rows.append(row)
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Identificación de sectores "importantes"
# --------------------------------------------------------------------------- #

def important_sectors(
    df: pd.DataFrame,
    indicator: str,
    scenario: str,
    *,
    n: int = 5,
) -> pd.DataFrame:
    """
    Devuelve los sectores que más contribuyen (en valor absoluto) al cambio
    del indicador en el escenario. Inspirado en el análisis de "coeficientes
    importantes" de Miller & Blair (2009, cap. 12).
    """
    base = df[(df["indicator"] == indicator) & (df["scenario"] == "baseline")]
    sc = df[(df["indicator"] == indicator) & (df["scenario"] == scenario)]
    base_g = base.groupby("sector", as_index=False)["value"].sum().rename(columns={"value": "baseline"})
    sc_g = sc.groupby("sector", as_index=False)["value"].sum().rename(columns={"value": "scenario"})

    out = base_g.merge(sc_g, on="sector", how="outer").fillna(0.0)
    out["delta_abs"] = out["scenario"] - out["baseline"]
    total_delta = out["delta_abs"].abs().sum()
    out["share_of_change"] = out["delta_abs"].abs() / total_delta if total_delta else 0.0
    out = out.sort_values("share_of_change", ascending=False).reset_index(drop=True)
    return out.head(n)
