"""
Generador de datos sintéticos compatibles con la salida de pycirk.

Produce un baseline y varios escenarios circulares con la misma estructura que
generaría el motor real (pycirk + EXIOBASE 3.3.sm), pero con dimensiones reducidas
y valores fabricados de forma reproducible. El esquema es deliberadamente compatible
con la salida real de pycirk para que el dashboard pueda intercambiar la fuente
sin tocar la capa de visualización.

Esquema de salida (formato largo):
    scenario | region | sector | indicator | value | unit | analysis

Donde:
    - scenario:  identificador del escenario (baseline o uno circular)
    - region:    región/país (12 categorías agregadas)
    - sector:    sector económico (20 categorías agregadas)
    - indicator: variable medida (VA, empleo, CO2eq, materiales, energía)
    - value:     valor numérico
    - unit:      unidad (M€, kpersonas, Mt CO2eq, Mt, TJ)
    - analysis:  'hotspot' (donde ocurre) o 'contribution' (consumo final)

Uso:
    python scripts/generate_synthetic_data.py
    # Genera ./data/synthetic/{baseline,esc_*}.parquet y metadata.json
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------- #
# Configuración del universo simulado
# --------------------------------------------------------------------------- #

# 12 regiones agregadas — refleja la práctica común de aplastar EU-27 + economías clave
REGIONS = [
    "España", "Alemania", "Francia", "Italia", "Polonia",  # UE-27 (top 5)
    "Resto UE-27",
    "Reino Unido", "Estados Unidos", "China", "Japón", "India",
    "Resto del mundo",
]

# 20 sectores — agregación didáctica de los 200 productos de EXIOBASE
SECTORS = [
    "Agricultura y pesca",
    "Minería y extracción",
    "Alimentación y bebidas",
    "Textil y calzado",
    "Madera, papel e imprenta",
    "Productos químicos",
    "Refino y combustibles",
    "Plásticos y caucho",
    "Acero y metalurgia primaria",
    "Acero secundario y reciclaje",
    "Maquinaria y equipos",
    "Equipos electrónicos",
    "Vehículos y partes",
    "Construcción",
    "Comercio mayorista y minorista",
    "Transporte y logística",
    "Energía y suministros",
    "Servicios financieros y empresariales",
    "Salud y educación",
    "Otros servicios",
]

# Indicadores: tres económicos, tres ambientales (lo justo para un dashboard útil)
INDICATORS = [
    {"id": "value_added", "label": "Valor Añadido", "unit": "M€", "kind": "econ"},
    {"id": "employment",  "label": "Empleo",        "unit": "kpersonas", "kind": "econ"},
    {"id": "output",      "label": "Producción",    "unit": "M€", "kind": "econ"},
    {"id": "co2eq",       "label": "Emisiones CO₂eq", "unit": "Mt CO₂eq", "kind": "env"},
    {"id": "materials",   "label": "Uso de materiales", "unit": "Mt", "kind": "env"},
    {"id": "energy",      "label": "Consumo energético", "unit": "TJ", "kind": "env"},
]

# Escenarios circulares modelados como modificaciones relativas
@dataclass
class Scenario:
    id: str
    label: str
    description: str
    # Sectores afectados directamente y multiplicador relativo aplicado a su producción
    sector_shocks: dict[str, float]
    # Cambios en intensidades de impacto ambiental (multiplicador por sector e indicador)
    intensity_shocks: dict[tuple[str, str], float]
    # Efecto relativo sobre el empleo del sector afectado (modelo lineal sencillo)
    employment_factor: dict[str, float]

SCENARIOS: list[Scenario] = [
    Scenario(
        id="esc_vida_util_vehiculos_10",
        label="+10 % vida útil vehículos",
        description=(
            "Prolongar un 10 % la vida útil del parque automovilístico reduce las ventas de "
            "vehículos nuevos y aumenta los servicios de reparación y mantenimiento."
        ),
        sector_shocks={
            "Vehículos y partes": -0.06,
            "Acero y metalurgia primaria": -0.02,
            "Plásticos y caucho": -0.01,
            "Comercio mayorista y minorista": +0.02,
            "Transporte y logística": +0.01,
            "Otros servicios": +0.04,
        },
        intensity_shocks={
            ("Vehículos y partes", "co2eq"): 0.95,
            ("Acero y metalurgia primaria", "co2eq"): 0.97,
        },
        employment_factor={
            "Vehículos y partes": -0.04,
            "Otros servicios": +0.05,
            "Comercio mayorista y minorista": +0.02,
        },
    ),
    Scenario(
        id="esc_vida_util_vehiculos_50",
        label="+50 % vida útil vehículos",
        description=(
            "Escenario disruptivo: se prolonga la vida útil un 50 %, lo que provoca caídas "
            "marcadas en cadenas primarias y un fuerte trasvase a servicios de reparación."
        ),
        sector_shocks={
            "Vehículos y partes": -0.25,
            "Acero y metalurgia primaria": -0.08,
            "Plásticos y caucho": -0.05,
            "Comercio mayorista y minorista": +0.06,
            "Transporte y logística": +0.04,
            "Otros servicios": +0.18,
        },
        intensity_shocks={
            ("Vehículos y partes", "co2eq"): 0.80,
            ("Acero y metalurgia primaria", "co2eq"): 0.92,
        },
        employment_factor={
            "Vehículos y partes": -0.18,
            "Otros servicios": +0.22,
            "Comercio mayorista y minorista": +0.07,
        },
    ),
    Scenario(
        id="esc_acero_secundario_30",
        label="+30 % acero secundario",
        description=(
            "Aumento del 30 % en la cuota de acero procedente del reciclaje, sustituyendo al "
            "acero primario en sectores intensivos en metal."
        ),
        sector_shocks={
            "Acero y metalurgia primaria": -0.10,
            "Acero secundario y reciclaje": +0.30,
            "Vehículos y partes": +0.00,
            "Construcción": +0.00,
        },
        intensity_shocks={
            ("Acero y metalurgia primaria", "co2eq"): 0.90,
            ("Acero secundario y reciclaje", "co2eq"): 0.95,
            ("Acero y metalurgia primaria", "energy"): 0.92,
        },
        employment_factor={
            "Acero secundario y reciclaje": +0.20,
            "Acero y metalurgia primaria": -0.05,
        },
    ),
    Scenario(
        id="esc_eficiencia_energetica_20",
        label="+20 % eficiencia energética",
        description=(
            "Mejora del 20 % en la eficiencia energética de los sectores intensivos. "
            "Reduce el consumo y las emisiones sin variar la producción."
        ),
        sector_shocks={},  # producción no cambia
        intensity_shocks={
            ("Energía y suministros", "energy"): 0.80,
            ("Energía y suministros", "co2eq"): 0.78,
            ("Productos químicos", "energy"): 0.85,
            ("Acero y metalurgia primaria", "energy"): 0.85,
            ("Construcción", "energy"): 0.90,
        },
        employment_factor={},
    ),
]

# --------------------------------------------------------------------------- #
# Generación del baseline
# --------------------------------------------------------------------------- #

def _region_weights(rng: np.random.Generator) -> np.ndarray:
    """Pesos macroeconómicos relativos por región (suman ~1)."""
    base = np.array([0.05, 0.18, 0.12, 0.10, 0.04, 0.18,  # UE
                     0.08, 0.20, 0.22, 0.07, 0.06, 0.30])  # resto del mundo
    base = base + rng.normal(0, 0.01, size=len(base))
    return base / base.sum()

def _sector_weights(rng: np.random.Generator) -> np.ndarray:
    """Pesos sectoriales orientativos sobre la producción total."""
    weights = np.array([
        0.04, 0.03, 0.06, 0.03, 0.03,   # primarios + ligeros
        0.05, 0.04, 0.03, 0.05, 0.01,   # químicos / metales
        0.05, 0.05, 0.06, 0.08,         # bienes y construcción
        0.10, 0.07, 0.05,               # comercio / transporte / energía
        0.10, 0.04, 0.03,               # servicios
    ])
    weights = weights + rng.normal(0, 0.003, size=len(weights))
    return weights / weights.sum()

def _intensity_table(rng: np.random.Generator) -> dict[str, np.ndarray]:
    """
    Intensidades de impacto por sector (impacto por M€ de producción).
    Se devuelve un dict: indicator_id -> array (n_sectors,)
    """
    n = len(SECTORS)
    sector_idx = {s: i for i, s in enumerate(SECTORS)}

    # CO2eq: alto en energía, refino, metalurgia, construcción
    co2 = rng.uniform(20, 60, size=n)
    co2[sector_idx["Energía y suministros"]] = 800
    co2[sector_idx["Refino y combustibles"]] = 600
    co2[sector_idx["Acero y metalurgia primaria"]] = 700
    co2[sector_idx["Acero secundario y reciclaje"]] = 250
    co2[sector_idx["Productos químicos"]] = 350
    co2[sector_idx["Construcción"]] = 180
    co2[sector_idx["Transporte y logística"]] = 250

    # Materiales: alto en construcción, metalurgia, vehículos
    mat = rng.uniform(0.5, 3.0, size=n)
    mat[sector_idx["Construcción"]] = 35
    mat[sector_idx["Acero y metalurgia primaria"]] = 28
    mat[sector_idx["Acero secundario y reciclaje"]] = 22
    mat[sector_idx["Vehículos y partes"]] = 18
    mat[sector_idx["Maquinaria y equipos"]] = 10

    # Energía: alta en energía, refino, metalurgia
    en = rng.uniform(80, 200, size=n)
    en[sector_idx["Energía y suministros"]] = 6000
    en[sector_idx["Refino y combustibles"]] = 4000
    en[sector_idx["Acero y metalurgia primaria"]] = 3500
    en[sector_idx["Productos químicos"]] = 2500
    en[sector_idx["Construcción"]] = 800

    # Empleo (kpersonas por M€): alto en agricultura, servicios, comercio
    emp = rng.uniform(2, 6, size=n)
    emp[sector_idx["Agricultura y pesca"]] = 18
    emp[sector_idx["Salud y educación"]] = 14
    emp[sector_idx["Servicios financieros y empresariales"]] = 8
    emp[sector_idx["Comercio mayorista y minorista"]] = 12
    emp[sector_idx["Otros servicios"]] = 10
    emp[sector_idx["Construcción"]] = 9

    # Valor añadido (% de la producción)
    va = rng.uniform(0.30, 0.45, size=n)
    va[sector_idx["Servicios financieros y empresariales"]] = 0.55
    va[sector_idx["Salud y educación"]] = 0.60
    va[sector_idx["Refino y combustibles"]] = 0.20
    va[sector_idx["Acero y metalurgia primaria"]] = 0.25

    return {
        "co2eq": co2,
        "materials": mat,
        "energy": en,
        "employment": emp,
        "value_added_ratio": va,
    }


def build_baseline(year: int = 2011, seed: int = 42, total_output_meur: float = 80_000_000.0) -> pd.DataFrame:
    """
    Construye un baseline en formato largo.
    total_output_meur: producción mundial total (orden de magnitud realista para 2011 ~ 80 T€).
    """
    rng = np.random.default_rng(seed)
    region_w = _region_weights(rng)
    sector_w = _sector_weights(rng)
    intensities = _intensity_table(rng)

    # Producción por (región, sector). Se introduce ruido para que los rankings sean realistas.
    prod = total_output_meur * np.outer(region_w, sector_w)
    prod *= 1 + rng.normal(0, 0.05, size=prod.shape)
    prod = np.clip(prod, 1.0, None)

    rows: list[dict] = []
    for ri, region in enumerate(REGIONS):
        for si, sector in enumerate(SECTORS):
            output_v = float(prod[ri, si])
            va = output_v * float(intensities["value_added_ratio"][si])
            emp = output_v / 1000 * float(intensities["employment"][si])  # kpers
            co2 = output_v / 1_000_000 * float(intensities["co2eq"][si])  # Mt
            mat = output_v / 1_000_000 * float(intensities["materials"][si])
            en = output_v / 1000 * float(intensities["energy"][si])  # TJ

            rows.extend([
                {"region": region, "sector": sector, "indicator": "output",      "value": output_v, "unit": "M€"},
                {"region": region, "sector": sector, "indicator": "value_added", "value": va,        "unit": "M€"},
                {"region": region, "sector": sector, "indicator": "employment",  "value": emp,       "unit": "kpersonas"},
                {"region": region, "sector": sector, "indicator": "co2eq",       "value": co2,       "unit": "Mt CO₂eq"},
                {"region": region, "sector": sector, "indicator": "materials",   "value": mat,       "unit": "Mt"},
                {"region": region, "sector": sector, "indicator": "energy",      "value": en,        "unit": "TJ"},
            ])

    df = pd.DataFrame(rows)
    df["scenario"] = "baseline"
    df["year"] = year
    df["analysis"] = "hotspot"
    return df[["scenario", "year", "analysis", "region", "sector", "indicator", "value", "unit"]]


# --------------------------------------------------------------------------- #
# Aplicación de un escenario sobre el baseline
# --------------------------------------------------------------------------- #

def apply_scenario(baseline: pd.DataFrame, scenario: Scenario) -> pd.DataFrame:
    """
    Aplica los shocks de un escenario sobre el baseline.

    Lógica simplificada (modelo lineal):
    1. La producción de los sectores con sector_shocks se multiplica por (1 + shock).
    2. El valor añadido y la producción cambian proporcionalmente.
    3. El empleo cambia con employment_factor (si no se define, sigue la producción).
    4. Las intensidades ambientales se modifican con intensity_shocks (multiplicador
       sobre el valor por unidad de producción) y luego se reescalan con la nueva producción.
    """
    df = baseline.copy()
    df["scenario"] = scenario.id

    # --- 1. Reescalado de la producción y el valor añadido ---
    for sector, shock in scenario.sector_shocks.items():
        mask = (df["sector"] == sector) & (df["indicator"].isin(["output", "value_added"]))
        df.loc[mask, "value"] *= (1 + shock)

    # --- 2. Empleo: por defecto sigue a la producción; si hay factor explícito, sustituye ---
    for sector, shock in scenario.sector_shocks.items():
        mask = (df["sector"] == sector) & (df["indicator"] == "employment")
        df.loc[mask, "value"] *= (1 + shock)
    for sector, factor in scenario.employment_factor.items():
        mask = (df["sector"] == sector) & (df["indicator"] == "employment")
        # se sustituye lo que hubiera puesto el sector_shock por el factor explícito
        baseline_mask = (baseline["sector"] == sector) & (baseline["indicator"] == "employment")
        df.loc[mask, "value"] = baseline.loc[baseline_mask, "value"].values * (1 + factor)

    # --- 3. Indicadores ambientales: primero reescalar por producción, luego por intensidad ---
    env = ["co2eq", "materials", "energy"]
    for sector, shock in scenario.sector_shocks.items():
        mask = (df["sector"] == sector) & (df["indicator"].isin(env))
        df.loc[mask, "value"] *= (1 + shock)
    for (sector, indicator), factor in scenario.intensity_shocks.items():
        mask = (df["sector"] == sector) & (df["indicator"] == indicator)
        df.loc[mask, "value"] *= factor

    return df


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #

def _save_dataframe(df: pd.DataFrame, base_path: Path) -> str:
    """
    Guarda el dataframe como Parquet si pyarrow está disponible; si no, como CSV.
    Devuelve la extensión usada (".parquet" o ".csv").
    """
    try:
        df.to_parquet(base_path.with_suffix(".parquet"), index=False)
        return ".parquet"
    except (ImportError, ValueError, Exception):
        df.to_csv(base_path.with_suffix(".csv"), index=False)
        return ".csv"


def main(out_dir: Path | None = None) -> None:
    out_dir = out_dir or Path(__file__).resolve().parent.parent / "data" / "synthetic"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Generando datos sintéticos en {out_dir}")
    baseline = build_baseline()
    ext = _save_dataframe(baseline, out_dir / "baseline")
    print(f"  ✓ baseline{ext} ({len(baseline):,} filas)")

    all_data = [baseline]
    for sc in SCENARIOS:
        df_sc = apply_scenario(baseline, sc)
        _save_dataframe(df_sc, out_dir / sc.id)
        all_data.append(df_sc)
        print(f"  ✓ {sc.id}{ext} ({len(df_sc):,} filas)")

    # Tabla consolidada (útil para el dashboard)
    consolidated = pd.concat(all_data, ignore_index=True)
    _save_dataframe(consolidated, out_dir / "all_scenarios")
    print(f"  ✓ all_scenarios{ext} ({len(consolidated):,} filas)")

    # Metadata
    metadata = {
        "regions": REGIONS,
        "sectors": SECTORS,
        "indicators": INDICATORS,
        "scenarios": [
            {"id": "baseline", "label": "Baseline", "description": "Escenario base (sin intervención)."},
        ] + [
            {"id": s.id, "label": s.label, "description": s.description}
            for s in SCENARIOS
        ],
        "years": [2011],
        "source": "synthetic",
        "schema": {
            "format": "long",
            "columns": ["scenario", "year", "analysis", "region", "sector", "indicator", "value", "unit"],
            "compatible_with": "pycirk + EXIOBASE 3.3.sm (intercambiable)",
        },
    }
    with open(out_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    print(f"  ✓ metadata.json")
    print(f"\nTotal: {len(REGIONS)} regiones × {len(SECTORS)} sectores × "
          f"{len(INDICATORS)} indicadores × {1 + len(SCENARIOS)} escenarios = "
          f"{len(consolidated):,} filas.")


if __name__ == "__main__":
    main()
