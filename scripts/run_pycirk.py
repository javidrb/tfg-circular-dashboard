"""
Ejecuta pycirk sobre EXIOBASE 3.3 para producir el baseline y los escenarios
circulares del TFG, y vuelca los resultados al formato canónico del dashboard.

Uso típico:
    # 1. Asegúrate de que pycirk está instalado y EXIOBASE descargada
    # 2. Edita el archivo scenarios.xlsx siguiendo la convención del MVP
    #    (ver docs/PYCIRK_SETUP.md)
    # 3. Lanza:
    python scripts/run_pycirk.py --aggregation bi-regional

Salida:
    data/pycirk_runs/baseline.parquet
    data/pycirk_runs/esc_*.parquet
    data/pycirk_runs/all_scenarios.parquet
    data/pycirk_runs/metadata.json

Notas de diseño:
    - El script invoca pycirk como subproceso (CLI) en lugar de importarlo
      como módulo. Esto evita arrastrar todas sus dependencias al dashboard
      y aísla cualquier crash de pycirk del proceso principal.
    - El parseo de la salida es robusto a varios formatos (CSV, HDF5)
      porque la versión de pycirk puede variar.
    - Si pycirk no está instalado, el script lo dice claramente y propone
      el comando de instalación.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

# --------------------------------------------------------------------------- #
# Configuración del MVP
# --------------------------------------------------------------------------- #

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = PROJECT_ROOT / "data" / "pycirk_runs"

# Mapping del nombre interno (que ya conoce el dashboard) al ID de escenario en
# scenarios.xlsx (que se documenta en docs/PYCIRK_SETUP.md).
@dataclass(frozen=True)
class PycirkScenario:
    id: str            # ID interno (debe coincidir con el del dashboard)
    label: str
    pycirk_id: int     # ID en scenarios.xlsx (0 = baseline)
    description: str

SCENARIOS = [
    PycirkScenario("baseline", "Baseline", 0,
                   "Escenario base sin intervenciones."),
    PycirkScenario("esc_vida_util_vehiculos_10", "+10 % vida útil vehículos", 1,
                   "Prolongación del 10 % en la vida útil del parque automovilístico."),
    PycirkScenario("esc_vida_util_vehiculos_50", "+50 % vida útil vehículos", 2,
                   "Prolongación del 50 % (escenario disruptivo)."),
    PycirkScenario("esc_acero_secundario_30", "+30 % acero secundario", 3,
                   "Aumento del 30 % en la cuota de acero procedente del reciclaje."),
    PycirkScenario("esc_eficiencia_energetica_20", "+20 % eficiencia energética", 4,
                   "Mejora del 20 % en sectores intensivos en energía."),
]

# Mapping de columnas/indicadores de pycirk → nuestro nombre canónico.
# El nombre exacto en pycirk puede variar entre versiones. Mantenemos un dict
# editable para que el ajuste sea trivial.
INDICATOR_MAP = {
    # extensión pycirk           → nombre canónico  (unidad)
    "value_added": ("value_added", "M€"),
    "VA": ("value_added", "M€"),
    "employment_total": ("employment", "kpersonas"),
    "Employment_total": ("employment", "kpersonas"),
    "GHG_emissions_AR5": ("co2eq", "Mt CO₂eq"),
    "Domestic_extraction_used_total": ("materials", "Mt"),
    "Energy_carrier_use_total": ("energy", "TJ"),
    "output": ("output", "M€"),
}


# --------------------------------------------------------------------------- #
# Utilidades
# --------------------------------------------------------------------------- #

def _ensure_pycirk_installed() -> str:
    """Devuelve la ruta al ejecutable de pycirk; aborta si no está."""
    exe = shutil.which("pycirk")
    if exe is None:
        sys.exit(
            "ERROR: no he encontrado el comando `pycirk` en el PATH.\n"
            "Instálalo primero:\n"
            "    pip install pycirk\n"
            "y descarga EXIOBASE desde https://doi.org/10.5281/zenodo.4695823.\n"
            "Más detalles en docs/PYCIRK_SETUP.md."
        )
    return exe


def _save(df: pd.DataFrame, base_path: Path) -> str:
    """Igual que en generate_synthetic_data: Parquet si se puede, si no CSV."""
    try:
        df.to_parquet(base_path.with_suffix(".parquet"), index=False)
        return ".parquet"
    except Exception:
        df.to_csv(base_path.with_suffix(".csv"), index=False)
        return ".csv"


def _normalize_indicator(name: str) -> tuple[str, str] | None:
    """Devuelve (canonical_id, unit) o None si el indicador no nos interesa."""
    if name in INDICATOR_MAP:
        return INDICATOR_MAP[name]
    # Match insensible a mayúsculas
    for k, v in INDICATOR_MAP.items():
        if k.lower() == name.lower():
            return v
    return None


# --------------------------------------------------------------------------- #
# Conversión de la salida de pycirk al esquema del dashboard
# --------------------------------------------------------------------------- #

def _pycirk_output_to_long(
    raw: pd.DataFrame,
    scenario_id: str,
    year: int,
) -> pd.DataFrame:
    """
    Convierte una salida de pycirk al formato largo del dashboard.

    pycirk normalmente devuelve un DataFrame con MultiIndex (region, sector)
    en filas e indicadores en columnas. Este parser tolera varias formas
    típicas; si la versión de tu pycirk devuelve algo distinto, ajusta este
    bloque.
    """
    # Si el índice es MultiIndex (region, sector), reseteamos
    if isinstance(raw.index, pd.MultiIndex) and len(raw.index.names) >= 2:
        raw = raw.reset_index()

    # Normalizar nombres de columnas comunes
    rename = {}
    for c in raw.columns:
        cl = str(c).strip().lower()
        if cl in ("region", "country", "region_code", "country_code"):
            rename[c] = "region"
        elif cl in ("sector", "product", "industry", "category"):
            rename[c] = "sector"
    raw = raw.rename(columns=rename)

    if "region" not in raw.columns or "sector" not in raw.columns:
        raise ValueError(
            f"La salida de pycirk no contiene columnas region/sector reconocibles. "
            f"Columnas disponibles: {list(raw.columns)}"
        )

    # Pivot a largo: una fila por (region, sector, indicator)
    id_vars = ["region", "sector"]
    value_vars = [c for c in raw.columns if c not in id_vars]
    long = raw.melt(id_vars=id_vars, value_vars=value_vars,
                    var_name="indicator_raw", value_name="value")

    # Filtrar y mapear los indicadores que nos interesan
    rows = []
    for _, r in long.iterrows():
        canon = _normalize_indicator(r["indicator_raw"])
        if canon is None:
            continue
        ind_id, unit = canon
        rows.append({
            "scenario": scenario_id,
            "year": year,
            "analysis": "hotspot",
            "region": str(r["region"]),
            "sector": str(r["sector"]),
            "indicator": ind_id,
            "value": float(r["value"]),
            "unit": unit,
        })

    return pd.DataFrame(rows, columns=[
        "scenario", "year", "analysis", "region", "sector",
        "indicator", "value", "unit",
    ])


def _find_pycirk_output(scenario_pycirk_id: int, pycirk_data_dir: Path) -> Path:
    """
    Localiza el archivo de salida que pycirk acaba de producir.

    pycirk suele guardar resultados en su carpeta `data/results/` con
    nombres del estilo `scenario_<n>.csv` o `scenario_<n>.h5`. Este helper
    busca cualquier archivo que coincida.
    """
    candidates = list(pycirk_data_dir.rglob(f"*scenario_{scenario_pycirk_id}*"))
    candidates += list(pycirk_data_dir.rglob(f"*sc_{scenario_pycirk_id}*"))
    candidates += list(pycirk_data_dir.rglob(f"*sc{scenario_pycirk_id}*"))
    candidates = [c for c in candidates if c.suffix in (".csv", ".h5", ".hdf5", ".xlsx")]
    if not candidates:
        raise FileNotFoundError(
            f"No encuentro la salida del escenario {scenario_pycirk_id} dentro de "
            f"{pycirk_data_dir}. Comprueba que pycirk se ejecutó con `-s True -od True`."
        )
    # El archivo más reciente
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _read_pycirk_output(path: Path) -> pd.DataFrame:
    if path.suffix == ".csv":
        return pd.read_csv(path)
    if path.suffix in (".h5", ".hdf5"):
        return pd.read_hdf(path)
    if path.suffix == ".xlsx":
        return pd.read_excel(path, sheet_name=0)
    raise ValueError(f"Formato no soportado: {path.suffix}")


# --------------------------------------------------------------------------- #
# Orquestación
# --------------------------------------------------------------------------- #

def run_pycirk(scenario_pycirk_id: int, aggregation: str, exe: str) -> int:
    """Lanza pycirk para un escenario. Devuelve el exit code."""
    ag_flag = "1" if aggregation == "bi-regional" else "0"
    cmd = [
        exe,
        "-tm", "0",                       # product-by-product, ITA_TC
        "-dr", "",                        # default directory
        "-ag", ag_flag,
        "-sc", str(scenario_pycirk_id),
        "-s", "True",
        "-od", "True",
    ]
    print(f"  > {' '.join(cmd)}")
    r = subprocess.run(cmd, check=False)
    return r.returncode


def detect_pycirk_data_dir() -> Path:
    """
    pycirk guarda los resultados en su propia carpeta `data/`. Intentamos
    detectarla mirando los site-packages.
    """
    try:
        import pycirk  # type: ignore
        return Path(pycirk.__file__).parent / "data"
    except ImportError:
        sys.exit("ERROR: no puedo importar pycirk para detectar su directorio. "
                 "Instálalo con `pip install pycirk` y vuelve a intentarlo.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ejecuta pycirk para el TFG.")
    parser.add_argument("--aggregation", choices=["bi-regional", "full"],
                        default="bi-regional",
                        help="bi-regional (EU vs ROW, rápido) o full (49 regiones, lento).")
    parser.add_argument("--year", type=int, default=2011,
                        help="Año del baseline de EXIOBASE (por defecto 2011).")
    parser.add_argument("--skip-run", action="store_true",
                        help="No invoca pycirk; solo parsea las salidas existentes.")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    exe = _ensure_pycirk_installed()
    pycirk_data_dir = detect_pycirk_data_dir()

    print(f"pycirk:   {exe}")
    print(f"data dir: {pycirk_data_dir}")
    print(f"output:   {OUT_DIR}")
    print()

    # 1) Ejecutar cada escenario
    if not args.skip_run:
        for sc in SCENARIOS:
            print(f">> Escenario {sc.pycirk_id} ({sc.id})")
            rc = run_pycirk(sc.pycirk_id, args.aggregation, exe)
            if rc != 0:
                sys.exit(f"pycirk devolvió código {rc} en el escenario {sc.id}.")

    # 2) Parsear salidas y volcar al esquema canónico
    all_long = []
    for sc in SCENARIOS:
        out_path = _find_pycirk_output(sc.pycirk_id, pycirk_data_dir)
        print(f"<< {sc.id} ← {out_path.name}")
        raw = _read_pycirk_output(out_path)
        long = _pycirk_output_to_long(raw, sc.id, args.year)
        ext = _save(long, OUT_DIR / sc.id)
        all_long.append(long)
        print(f"   ({len(long):,} filas → {sc.id}{ext})")

    consolidated = pd.concat(all_long, ignore_index=True)
    _save(consolidated, OUT_DIR / "all_scenarios")
    print(f"\nConsolidado: {len(consolidated):,} filas → {OUT_DIR / 'all_scenarios.parquet'}")

    # 3) Metadatos
    regions = sorted(consolidated["region"].unique().tolist())
    sectors = sorted(consolidated["sector"].unique().tolist())
    indicators = sorted(consolidated["indicator"].unique().tolist())
    indicator_meta = []
    for ind_id in indicators:
        unit_row = consolidated[consolidated["indicator"] == ind_id].iloc[0]
        indicator_meta.append({
            "id": ind_id,
            "label": ind_id.replace("_", " ").title(),
            "unit": str(unit_row["unit"]),
            "kind": "econ" if ind_id in ("value_added", "employment", "output") else "env",
        })

    metadata = {
        "regions": regions,
        "sectors": sectors,
        "indicators": indicator_meta,
        "scenarios": [{"id": s.id, "label": s.label, "description": s.description} for s in SCENARIOS],
        "years": [args.year],
        "source": "pycirk",
        "aggregation": args.aggregation,
        "schema": {
            "format": "long",
            "columns": ["scenario", "year", "analysis", "region", "sector", "indicator", "value", "unit"],
            "compatible_with": "synthetic dataset (intercambiable)",
        },
    }
    with open(OUT_DIR / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    print(f"\nOK. El dashboard ahora detectará automáticamente los datos de pycirk.")
    print(f"    Reinicia Streamlit para ver el cambio.")


if __name__ == "__main__":
    main()
