"""
Capa de carga de datos del dashboard.

Aísla la diferencia entre datos sintéticos (para desarrollo) y datos reales
(producidos por pycirk). El resto del dashboard SÓLO conoce esta interfaz.
Cuando se conecte el motor real, lo único que cambia es la implementación
de `load_all` — la firma se mantiene idéntica.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pandas as pd

# --------------------------------------------------------------------------- #
# Localización del directorio de datos
# --------------------------------------------------------------------------- #

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SYNTHETIC_DIR = PROJECT_ROOT / "data" / "synthetic"
DEFAULT_PYCIRK_DIR = PROJECT_ROOT / "data" / "pycirk_runs"


@dataclass(frozen=True)
class DataBundle:
    """Snapshot in-memory de todos los datos que necesita el dashboard."""
    df: pd.DataFrame                       # tabla larga consolidada
    metadata: dict                         # regiones, sectores, indicadores, escenarios
    source: str                            # "synthetic" o "pycirk"


# --------------------------------------------------------------------------- #
# Cargadores concretos
# --------------------------------------------------------------------------- #

def _read_table(path_no_ext: Path) -> pd.DataFrame | None:
    """Lee Parquet si existe; si no, CSV. Devuelve None si no hay archivo."""
    parquet_path = path_no_ext.with_suffix(".parquet")
    csv_path = path_no_ext.with_suffix(".csv")
    if parquet_path.exists():
        try:
            return pd.read_parquet(parquet_path)
        except (ImportError, Exception):
            pass  # cae a CSV si pyarrow no está disponible
    if csv_path.exists():
        return pd.read_csv(csv_path)
    return None


def _load_from_dir(d: Path) -> DataBundle | None:
    """Carga un bundle desde un directorio si tiene la estructura esperada."""
    meta_file = d / "metadata.json"
    if not meta_file.exists():
        return None

    df = _read_table(d / "all_scenarios")
    if df is None:
        return None

    with open(meta_file, encoding="utf-8") as f:
        metadata = json.load(f)

    return DataBundle(df=df, metadata=metadata, source=metadata.get("source", "unknown"))


def _autogenerate_synthetic() -> None:
    """
    Llama al generador de datos sintéticos en proceso (sin subprocess).
    Útil cuando el dashboard arranca en un entorno limpio (Streamlit Cloud, CI).
    """
    import sys
    sys.path.insert(0, str(PROJECT_ROOT))
    try:
        from scripts.generate_synthetic_data import main as _gen
    except Exception:  # pragma: no cover
        sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
        from generate_synthetic_data import main as _gen  # type: ignore[no-redef]
    _gen()


@lru_cache(maxsize=1)
def load_all(prefer: str = "auto") -> DataBundle:
    """
    Carga el bundle consolidado.

    prefer = "auto":      intenta pycirk; si no, sintético; si tampoco, autogenera sintético.
    prefer = "synthetic": fuerza sintético (autogenera si falta).
    prefer = "pycirk":    fuerza pycirk (lanza FileNotFoundError si no existe).
    """
    if prefer == "pycirk":
        bundle = _load_from_dir(DEFAULT_PYCIRK_DIR)
        if bundle is None:
            raise FileNotFoundError(
                f"No se encontraron datos de pycirk en {DEFAULT_PYCIRK_DIR}. "
                "Ejecuta `python scripts/run_pycirk.py` primero."
            )
        return bundle

    if prefer == "synthetic":
        bundle = _load_from_dir(DEFAULT_SYNTHETIC_DIR)
        if bundle is None:
            _autogenerate_synthetic()
            bundle = _load_from_dir(DEFAULT_SYNTHETIC_DIR)
        if bundle is None:  # pragma: no cover
            raise FileNotFoundError(
                f"No se encontraron datos sintéticos en {DEFAULT_SYNTHETIC_DIR} "
                "y la auto-generación falló."
            )
        return bundle

    # auto: pycirk → sintético → autogenerar sintético
    bundle = _load_from_dir(DEFAULT_PYCIRK_DIR) or _load_from_dir(DEFAULT_SYNTHETIC_DIR)
    if bundle is None:
        _autogenerate_synthetic()
        bundle = _load_from_dir(DEFAULT_SYNTHETIC_DIR)
    if bundle is None:  # pragma: no cover
        raise FileNotFoundError(
            "No se encontraron datos y la auto-generación falló. "
            "Revisa scripts/generate_synthetic_data.py."
        )
    return bundle


# --------------------------------------------------------------------------- #
# Helpers de filtrado y agregación (lo que el dashboard consume)
# --------------------------------------------------------------------------- #

def filter_data(
    df: pd.DataFrame,
    *,
    scenario: str | None = None,
    region: str | list[str] | None = None,
    sector: str | list[str] | None = None,
    indicator: str | list[str] | None = None,
) -> pd.DataFrame:
    """Filtro vectorizado sobre el dataframe largo."""
    out = df
    if scenario is not None:
        out = out[out["scenario"] == scenario]
    if region is not None:
        regs = [region] if isinstance(region, str) else region
        out = out[out["region"].isin(regs)]
    if sector is not None:
        sects = [sector] if isinstance(sector, str) else sector
        out = out[out["sector"].isin(sects)]
    if indicator is not None:
        inds = [indicator] if isinstance(indicator, str) else indicator
        out = out[out["indicator"].isin(inds)]
    return out


def aggregate_indicator(df: pd.DataFrame, indicator: str, by: str = "region") -> pd.DataFrame:
    """Agrega un indicador a lo largo de la dimensión `by` (region o sector)."""
    sub = df[df["indicator"] == indicator]
    grouped = sub.groupby(["scenario", by], as_index=False)["value"].sum()
    return grouped


def total_indicator(df: pd.DataFrame, indicator: str, scenario: str) -> float:
    """Suma total de un indicador para un escenario."""
    sub = df[(df["indicator"] == indicator) & (df["scenario"] == scenario)]
    return float(sub["value"].sum())


def delta_vs_baseline(df: pd.DataFrame, indicator: str, scenario: str) -> tuple[float, float]:
    """
    Devuelve (variación absoluta, variación relativa) del indicador del escenario
    respecto al baseline.
    """
    base = total_indicator(df, indicator, "baseline")
    sc = total_indicator(df, indicator, scenario)
    abs_d = sc - base
    rel_d = (abs_d / base) if base else 0.0
    return abs_d, rel_d


def sector_breakdown(df: pd.DataFrame, indicator: str, scenario: str) -> pd.DataFrame:
    """Tabla sector → valor para un escenario e indicador."""
    sub = df[(df["indicator"] == indicator) & (df["scenario"] == scenario)]
    return (
        sub.groupby("sector", as_index=False)["value"]
        .sum()
        .sort_values("value", ascending=False)
        .reset_index(drop=True)
    )


def comparison_breakdown(
    df: pd.DataFrame, indicator: str, scenario: str, by: str = "sector"
) -> pd.DataFrame:
    """
    Tabla con valor baseline, valor escenario y variaciones absoluta/relativa
    desagregada por `by` (sector o region).

    Salida: columnas [by, baseline, scenario, delta_abs, delta_rel]
    """
    agg = aggregate_indicator(df, indicator, by=by)

    base = (
        agg[agg["scenario"] == "baseline"]
        .drop(columns="scenario")
        .rename(columns={"value": "baseline"})
    )
    sc = (
        agg[agg["scenario"] == scenario]
        .drop(columns="scenario")
        .rename(columns={"value": "_scen_val"})
    )

    out = base.merge(sc, on=by, how="outer").fillna(0.0)
    out["delta_abs"] = out["_scen_val"] - out["baseline"]
    out["delta_rel"] = out["delta_abs"] / out["baseline"].replace(0, pd.NA)
    out = out.rename(columns={"_scen_val": "scenario"})
    out = out[[by, "baseline", "scenario", "delta_abs", "delta_rel"]]
    return out.sort_values(
        "delta_rel", key=lambda s: s.fillna(0).abs(), ascending=False
    ).reset_index(drop=True)
