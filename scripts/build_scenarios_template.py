"""
Genera una plantilla de referencia con los 4 escenarios circulares del MVP,
como documentación legible. Sirve como referencia para rellenar el
`scenarios.xlsx` que pycirk genera por defecto cuando lo inicializas.

Uso:
    python scripts/build_scenarios_template.py
Salida:
    docs/scenarios_reference.xlsx   (referencia para humanos)
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

OUT = Path(__file__).resolve().parent.parent / "docs" / "scenarios_reference.xlsx"
OUT.parent.mkdir(parents=True, exist_ok=True)

# Estructura inspirada en la convención de pycirk: una fila por intervención.
# Las columnas reales de pycirk pueden variar entre versiones, así que usamos
# nombres descriptivos. Cuando rellenes el scenarios.xlsx oficial, mapea las
# columnas equivalentes.

scenarios_overview = pd.DataFrame([
    {
        "scenario_id": 0,
        "scenario_internal_id": "baseline",
        "label": "Baseline",
        "description": "Escenario base sin intervenciones. Reproduce EXIOBASE 3.3 tal cual.",
        "interventions": "(ninguna)",
    },
    {
        "scenario_id": 1,
        "scenario_internal_id": "esc_vida_util_vehiculos_10",
        "label": "+10 % vida útil vehículos",
        "description": "Prolongación del 10 % en la vida útil del parque automovilístico.",
        "interventions": "Reduce -6 % la demanda final de 'Motor vehicles, trailers and semi-trailers' "
                         "y compensa con +4 % en 'Other services'.",
    },
    {
        "scenario_id": 2,
        "scenario_internal_id": "esc_vida_util_vehiculos_50",
        "label": "+50 % vida útil vehículos",
        "description": "Escenario disruptivo: prolongación del 50 %.",
        "interventions": "Reduce -25 % la demanda final de 'Motor vehicles' y compensa con +18 % "
                         "en 'Other services' y +6 % en 'Wholesale and retail trade'.",
    },
    {
        "scenario_id": 3,
        "scenario_internal_id": "esc_acero_secundario_30",
        "label": "+30 % acero secundario",
        "description": "Aumento del 30 % en cuota de acero secundario en la matriz A.",
        "interventions": "Aumenta +30 % el coeficiente A[Secondary steel, Vehicles] y "
                         "reduce -8 % A[Primary steel, Vehicles] (compensación 1:1).",
    },
    {
        "scenario_id": 4,
        "scenario_internal_id": "esc_eficiencia_energetica_20",
        "label": "+20 % eficiencia energética",
        "description": "Mejora del 20 % en intensidades energéticas de sectores intensivos.",
        "interventions": "Multiplica por 0.80 los coeficientes ambientales 'Energy_carrier_use_total' "
                         "de Energía, Refino y Acero primario. La producción no cambia.",
    },
])

interventions_detail = pd.DataFrame([
    # scenario_id, intervention_id, matrix, kind, row_category, col_category, change_type, value
    (1, 1, "Y", "demand_change",     "Motor vehicles, trailers and semi-trailers", "EU final demand", "relative", -0.06),
    (1, 2, "Y", "demand_change",     "Other services",                              "EU final demand", "relative", +0.04),
    (1, 3, "Y", "demand_change",     "Wholesale and retail trade",                  "EU final demand", "relative", +0.02),
    (1, 4, "F", "intensity_change",  "GHG_emissions_AR5",                           "Motor vehicles", "relative", -0.05),

    (2, 1, "Y", "demand_change",     "Motor vehicles, trailers and semi-trailers", "EU final demand", "relative", -0.25),
    (2, 2, "Y", "demand_change",     "Other services",                              "EU final demand", "relative", +0.18),
    (2, 3, "Y", "demand_change",     "Wholesale and retail trade",                  "EU final demand", "relative", +0.06),
    (2, 4, "F", "intensity_change",  "GHG_emissions_AR5",                           "Motor vehicles", "relative", -0.20),
    (2, 5, "F", "intensity_change",  "GHG_emissions_AR5",                           "Basic iron and steel", "relative", -0.08),

    (3, 1, "A", "tech_coef_change",  "Secondary steel for treatment, reprocessing", "Motor vehicles", "relative", +0.30),
    (3, 2, "A", "tech_coef_change",  "Basic iron and steel and ferro-alloys",       "Motor vehicles", "relative", -0.08),
    (3, 3, "F", "intensity_change",  "GHG_emissions_AR5",                           "Basic iron and steel", "relative", -0.10),
    (3, 4, "F", "intensity_change",  "Energy_carrier_use_total",                    "Basic iron and steel", "relative", -0.08),

    (4, 1, "F", "intensity_change",  "Energy_carrier_use_total",                    "Energy and utilities", "relative", -0.20),
    (4, 2, "F", "intensity_change",  "GHG_emissions_AR5",                           "Energy and utilities", "relative", -0.22),
    (4, 3, "F", "intensity_change",  "Energy_carrier_use_total",                    "Chemicals",            "relative", -0.15),
    (4, 4, "F", "intensity_change",  "Energy_carrier_use_total",                    "Basic iron and steel", "relative", -0.15),
    (4, 5, "F", "intensity_change",  "Energy_carrier_use_total",                    "Construction",         "relative", -0.10),
], columns=[
    "scenario_id", "intervention_id", "matrix", "kind",
    "row_category", "col_category", "change_type", "value",
])

# Leyenda
legend = pd.DataFrame([
    ("matrix",      "A: matriz de coeficientes técnicos. Y: demanda final. F: intensidades ambientales."),
    ("kind",        "tech_coef_change: modifica receta productiva. demand_change: modifica consumo final. intensity_change: modifica vector ambiental."),
    ("row_category","Categoría de la fila a modificar (sector/producto/extensión)."),
    ("col_category","Categoría de la columna (sector consumidor o categoría de demanda)."),
    ("change_type", "relative: multiplicador (ej. -0.06 = -6 %). absolute: nuevo valor."),
    ("value",       "Magnitud del cambio."),
], columns=["columna", "significado"])

with pd.ExcelWriter(OUT, engine="openpyxl") as w:
    scenarios_overview.to_excel(w, sheet_name="scenarios", index=False)
    interventions_detail.to_excel(w, sheet_name="interventions", index=False)
    legend.to_excel(w, sheet_name="legend", index=False)

print(f"Plantilla generada: {OUT}")
print(f"  - hoja 'scenarios':      resumen de los 4 escenarios + baseline")
print(f"  - hoja 'interventions':  intervenciones detalladas por escenario")
print(f"  - hoja 'legend':         significado de las columnas")
print()
print("Uso: ábrela junto al scenarios.xlsx que genere pycirk en su carpeta data/,")
print("y mapea las intervenciones a las columnas equivalentes.")
