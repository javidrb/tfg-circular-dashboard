"""
Convierte la salida de pycirk (data.pkl) al esquema canónico del dashboard.

Reto resuelto en esta versión:
    - Baseline guarda matrices Cr_W, Cr_E, Cr_M, Cr_R con columnas tipo
      (region, code, full_name, abbreviation[, unit]).
    - Los escenarios guardan las mismas matrices con columnas enteras (0..399)
      y guardan Z, Y, M como ndarrays sin metadatos.
    - El orden de las 400 columnas (200 productos × 2 regiones) se mantiene.

Estrategia:
    1. Cargar el data.pkl baseline primero y construir un "column_meta": una
       lista de (region, sector) indexada por posición.
    2. Para cada escenario (incluido el baseline), extraer cada indicador
       mirando la posición de cada columna y traduciéndola con column_meta.

Uso:
    python scripts/convert_pycirk_output.py
    python scripts/convert_pycirk_output.py --path ~/Documents/pycirk
"""
from __future__ import annotations

import argparse
import json
import pickle
import re
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = PROJECT_ROOT / "data" / "pycirk_runs"


# --------------------------------------------------------------------------- #
# Configuración: cómo extraer los indicadores del dashboard
# --------------------------------------------------------------------------- #

EXTRACTORS = [
    # (matrix_key, predicate(idx) → True, indicator_id)
    ("Cr_W", lambda idx: idx[0] == "Value Added",                                                "value_added"),
    ("Cr_W", lambda idx: idx[0] == "Employment",                                                 "employment"),
    ("Cr_E", lambda idx: "global warming gwp100" in " ".join(str(x) for x in idx).lower(),       "co2eq"),
    ("Cr_M", lambda idx: "total emission relevant energy use" in " ".join(str(x) for x in idx).lower(), "energy"),
    ("Cr_R", lambda idx: idx[0] == "Land use",                                                   "land_use"),
]

INDICATOR_LABELS = {
    "value_added": ("Valor Añadido",     "M€",         "econ"),
    "employment":  ("Empleo",            "kpersonas",  "econ"),
    "output":      ("Producción",        "M€",         "econ"),
    "co2eq":       ("Emisiones CO₂eq",   "kg CO₂eq",   "env"),
    "energy":      ("Consumo energético","TJ",         "env"),
    "materials":   ("Uso de materiales", "kt",         "env"),
    "land_use":    ("Uso de tierra",     "km²",        "env"),
}


# --------------------------------------------------------------------------- #
# Extracción del column_meta desde el baseline
# --------------------------------------------------------------------------- #

def _column_to_region_sector(col) -> tuple[str, str] | None:
    if isinstance(col, tuple) and len(col) >= 3:
        region = str(col[0])
        sector = str(col[2])
        return region, sector
    return None


def build_column_meta(baseline_munch) -> list[tuple[str, str]]:
    """
    Construye una lista de (region, sector) de longitud 400, indexada por la
    posición de columna en el modelo IO bi-regional.

    Lo deducimos preferentemente de Cr_W (que en baseline tiene columnas
    como tuplas (region, code, name, abbr)). Si Cr_W no tiene tuplas (raro),
    intentamos con Cr_E o Z.
    """
    candidates = ["Cr_W", "Cr_E", "Cr_M", "Cr_R", "Z"]
    for key in candidates:
        if key not in baseline_munch:
            continue
        mat = baseline_munch[key]
        if not isinstance(mat, pd.DataFrame):
            continue
        if len(mat.columns) == 0:
            continue
        first_col = mat.columns[0]
        if isinstance(first_col, tuple) and len(first_col) >= 3:
            return [
                _column_to_region_sector(c) or (f"col_{i}", f"col_{i}")
                for i, c in enumerate(mat.columns)
            ]
    raise RuntimeError(
        "No conseguí extraer column_meta del baseline (ninguna matriz tiene columnas tipo tupla)."
    )


# --------------------------------------------------------------------------- #
# Convertir una Munch en filas largas (usando column_meta del baseline)
# --------------------------------------------------------------------------- #

def _index_to_unit(idx) -> str:
    if not isinstance(idx, tuple):
        return ""
    return str(idx[-1])


def _matrix_values(mat, expected_cols: int) -> np.ndarray | None:
    """
    Devuelve los valores de la matriz como ndarray 2D (filas × cols).
    Acepta DataFrame o ndarray. Devuelve None si no encaja con expected_cols.
    """
    if isinstance(mat, pd.DataFrame):
        return mat.values
    if isinstance(mat, np.ndarray):
        if mat.ndim != 2:
            return None
        return mat
    return None


def _find_row_positions_in_dataframe(df: pd.DataFrame, predicate) -> list[int]:
    return [i for i, idx in enumerate(df.index) if predicate(idx)]


def _override_unit(indicator_id: str, raw_unit: str) -> str:
    """Para que las unidades del dashboard sean homogéneas y bonitas."""
    canonical = INDICATOR_LABELS.get(indicator_id, ("", "", ""))[1]
    return canonical or raw_unit


def munch_to_long(
    munch_obj,
    scenario_id: str,
    column_meta: list[tuple[str, str]],
    year: int = 2011,
) -> pd.DataFrame:
    rows: list[dict] = []
    n_cols = len(column_meta)

    # ------------------- 1. Indicadores extraídos de Cr_* DataFrames ----------- #
    for matrix_key, predicate, ind_id in EXTRACTORS:
        mat = munch_obj.get(matrix_key)
        if mat is None or not isinstance(mat, pd.DataFrame):
            print(f"  [warn] {scenario_id}: matriz {matrix_key} no es DataFrame, salto {ind_id}")
            continue
        if mat.shape[1] != n_cols:
            print(f"  [warn] {scenario_id}: {matrix_key} tiene {mat.shape[1]} cols (esperaba {n_cols}), salto {ind_id}")
            continue

        positions = _find_row_positions_in_dataframe(mat, predicate)
        if not positions:
            # En escenarios podemos no encontrar la fila si pycirk la elimina; intentamos por nombre crudo
            print(f"  [warn] {scenario_id}: no encontré fila para {ind_id} en {matrix_key}")
            continue

        values = mat.values  # 2D ndarray
        idx_list = list(mat.index)
        for pos in positions:
            unit = _override_unit(ind_id, _index_to_unit(idx_list[pos]))
            row_vals = values[pos]
            for ci in range(n_cols):
                v = row_vals[ci]
                try:
                    fv = float(v)
                except (TypeError, ValueError):
                    continue
                region, sector = column_meta[ci]
                rows.append({
                    "scenario": scenario_id, "year": year, "analysis": "hotspot",
                    "region": region, "sector": sector,
                    "indicator": ind_id, "value": fv,
                    "unit": unit,
                })

    # ------------------- 2. Producción total (output) -------------------------- #
    z = munch_obj.get("Z"); y = munch_obj.get("Y")
    z_arr = _matrix_values(z, n_cols) if z is not None else None
    y_arr = _matrix_values(y, n_cols) if y is not None else None
    # Z es 400×400, Y es 400×14 → producción total (filas) = sum(Z, axis=1) + sum(Y, axis=1)
    if z_arr is not None and z_arr.shape[0] == n_cols:
        total = z_arr.sum(axis=1)
        if y_arr is not None and y_arr.shape[0] == n_cols:
            total = total + y_arr.sum(axis=1)
        for ci in range(n_cols):
            try:
                fv = float(total[ci])
            except (TypeError, ValueError):
                continue
            region, sector = column_meta[ci]
            rows.append({
                "scenario": scenario_id, "year": year, "analysis": "hotspot",
                "region": region, "sector": sector,
                "indicator": "output", "value": fv,
                "unit": INDICATOR_LABELS["output"][1],
            })
    else:
        print(f"  [warn] {scenario_id}: no pude calcular 'output' (Z/Y ausentes o con shape inesperado)")

    # ------------------- 3. Materiales (suma de M por columna) ----------------- #
    m = munch_obj.get("M")
    m_arr = _matrix_values(m, n_cols) if m is not None else None
    if m_arr is not None and m_arr.shape[1] == n_cols:
        total_m = m_arr.sum(axis=0)
        for ci in range(n_cols):
            try:
                fv = float(total_m[ci])
            except (TypeError, ValueError):
                continue
            region, sector = column_meta[ci]
            rows.append({
                "scenario": scenario_id, "year": year, "analysis": "hotspot",
                "region": region, "sector": sector,
                "indicator": "materials", "value": fv,
                "unit": INDICATOR_LABELS["materials"][1],
            })
    else:
        print(f"  [warn] {scenario_id}: no pude calcular 'materials' (M ausente o con shape inesperado)")

    return pd.DataFrame(rows, columns=[
        "scenario", "year", "analysis", "region", "sector", "indicator", "value", "unit",
    ])


# --------------------------------------------------------------------------- #
# Descubrimiento de archivos y persistencia
# --------------------------------------------------------------------------- #

def discover_pycirk_outputs(base_dir: Path) -> list[tuple[str, Path]]:
    """
    Recorre base_dir buscando data.pkl. Devuelve [(scenario_id, ruta), ...].

    Estructura esperada: base_dir/<output_YYYY_M_D>/<scenario_name>/<HH_MM>/data.pkl
    Si hay varios timestamps por escenario, nos quedamos con el más reciente.
    El baseline siempre va primero (es la fuente de column_meta).
    """
    found: dict[str, tuple[float, Path]] = {}
    for pkl in base_dir.rglob("data.pkl"):
        scen_dir = pkl.parent.parent
        scen_name = scen_dir.name
        mtime = pkl.stat().st_mtime
        if scen_name not in found or mtime > found[scen_name][0]:
            found[scen_name] = (mtime, pkl)

    result: list[tuple[str, Path]] = []
    for name, (_, path) in found.items():
        sid = _normalize_scenario_id(name)
        result.append((sid, path))
    result.sort(key=lambda t: (0 if t[0] == "baseline" else 1, t[0]))
    return result


def _normalize_scenario_id(folder_name: str) -> str:
    s = folder_name.strip().lower()
    if s == "baseline":
        return "baseline"
    m = re.match(r"scenario[_\s\-]?(\d+)", s)
    if m:
        return f"scenario_{m.group(1)}"
    return s.replace(" ", "_")


def _save(df: pd.DataFrame, base_path: Path) -> str:
    try:
        df.to_parquet(base_path.with_suffix(".parquet"), index=False)
        return ".parquet"
    except Exception:
        df.to_csv(base_path.with_suffix(".csv"), index=False)
        return ".csv"


def _safe_unique(seq: Iterable) -> list:
    seen, out = set(), []
    for x in seq:
        if x not in seen:
            seen.add(x); out.append(x)
    return out


def write_metadata(consolidated: pd.DataFrame, scenarios_seen: list[str]) -> None:
    regions = _safe_unique(sorted(consolidated["region"].unique().tolist()))
    sectors = _safe_unique(sorted(consolidated["sector"].unique().tolist()))

    indicator_meta = []
    for ind in consolidated["indicator"].unique().tolist():
        label, unit_default, kind = INDICATOR_LABELS.get(
            ind, (ind.replace("_", " ").title(), "", "econ"),
        )
        # Si el converter dejó otra unidad concreta, respetamos lo que vino
        sub = consolidated[consolidated["indicator"] == ind]
        unit = sub.iloc[0]["unit"] or unit_default
        indicator_meta.append({"id": ind, "label": label, "unit": unit, "kind": kind})

    descriptions = {
        "baseline":   "Baseline EXIOBASE 3.3 bi-regional (EU vs Resto del Mundo, 2011) sin intervención.",
        "scenario_1": "Reuse, remanufacturing y refurbishment (Donati et al., 2020): 11 intervenciones reduciendo demanda de acero/aluminio/maquinaria primarios y aumentando reparación.",
        "scenario_2": "Boost acero secundario: sustitución del acero primario por secundario en vehículos, construcción y maquinaria (3 pares Primary+Ancillary, ±25–30 %).",
        "scenario_3": "Vida útil del parque automovilístico EU +50 %: reducción de demanda final de vehículos en la UE compensada con servicios de reparación; reducción de inputs primarios (acero, aluminio) en fabricación de vehículos compensada también con reparación.",
    }
    scenarios_meta = []
    for sid in scenarios_seen:
        scenarios_meta.append({
            "id": sid,
            "label": "Baseline" if sid == "baseline" else sid.replace("_", " ").capitalize(),
            "description": descriptions.get(sid, f"Escenario circular #{sid} de scenarios.xlsx (pycirk)."),
        })

    metadata = {
        "regions": regions,
        "sectors": sectors,
        "indicators": indicator_meta,
        "scenarios": scenarios_meta,
        "years": _safe_unique(consolidated["year"].astype(int).unique().tolist()),
        "source": "pycirk",
        "aggregation": "bi-regional",
        "schema": {
            "format": "long",
            "columns": ["scenario", "year", "analysis", "region", "sector",
                        "indicator", "value", "unit"],
            "compatible_with": "synthetic dataset (intercambiable)",
        },
    }
    with open(OUT_DIR / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #

def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--path", type=Path, default=Path.home() / "Documents" / "pycirk",
                   help="Directorio raíz de salidas de pycirk (por defecto ~/Documents/pycirk).")
    p.add_argument("--year", type=int, default=2011)
    args = p.parse_args()

    if not args.path.exists():
        print(f"ERROR: no existe {args.path}")
        return

    print(f">> Buscando data.pkl en {args.path}")
    discovered = discover_pycirk_outputs(args.path)
    if not discovered:
        print("   (no se encontró ningún data.pkl)")
        return

    # Necesitamos el baseline primero para construir el column_meta
    baseline_entry = next((e for e in discovered if e[0] == "baseline"), None)
    if baseline_entry is None:
        print("ERROR: no encontré baseline en los outputs. Lanza pycirk con `-sc 0` primero.")
        return

    print(f"\n>> Cargando baseline para extraer column_meta: {baseline_entry[1]}")
    with open(baseline_entry[1], "rb") as f:
        baseline_obj = pickle.load(f)
    column_meta = build_column_meta(baseline_obj)
    print(f"   column_meta listo: {len(column_meta)} posiciones, "
          f"regiones={_safe_unique(r for r, _ in column_meta)}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    all_long: list[pd.DataFrame] = []
    seen: list[str] = []

    for sid, pkl_path in discovered:
        print(f"\n>> {sid} ← {pkl_path}")
        if sid == "baseline":
            obj = baseline_obj
        else:
            with open(pkl_path, "rb") as f:
                obj = pickle.load(f)
        long_df = munch_to_long(obj, scenario_id=sid, column_meta=column_meta, year=args.year)
        ext = _save(long_df, OUT_DIR / sid)
        all_long.append(long_df)
        seen.append(sid)
        print(f"   ({len(long_df):,} filas → {sid}{ext})")

    consolidated = pd.concat(all_long, ignore_index=True)
    _save(consolidated, OUT_DIR / "all_scenarios")
    write_metadata(consolidated, seen)

    print(f"\n=== RESUMEN ===")
    print(f"Escenarios:  {len(seen)}  -> {seen}")
    print(f"Indicadores: {sorted(consolidated['indicator'].unique().tolist())}")
    print(f"Regiones:    {sorted(consolidated['region'].unique().tolist())}")
    print(f"Sectores:    {len(consolidated['sector'].unique())} categorías")
    print(f"Total filas: {len(consolidated):,}")
    print(f"\nGuardado en: {OUT_DIR}")
    print("Recarga Streamlit para ver los datos reales (la app prefiere pycirk_runs sobre synthetic).")


if __name__ == "__main__":
    main()
