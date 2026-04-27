"""
[PLACEHOLDER — Fase F3 del plan del TFG]

Script que ejecutará pycirk sobre EXIOBASE 3.3.sm para producir el baseline
y los escenarios circulares reales que sustituirán a los datos sintéticos.

Esquema previsto (que ya respeta el dashboard):

    scenario | year | analysis | region | sector | indicator | value | unit

Pasos pendientes (a desarrollar cuando se aborde F3):
    1. Resolver la instalación de pycirk (probablemente desde GitHub, no PyPI).
    2. Descargar EXIOBASE 3.3.sm desde Zenodo (DOI 10.5281/zenodo.3533196).
    3. Definir un YAML de escenarios por cada palanca del MVP.
    4. Ejecutar pycirk en bucle y volcar la salida en data/pycirk_runs/.
    5. Reorganizar los DataFrames a formato largo (melt) y guardar en Parquet.
    6. Generar metadata.json con la lista de regiones/sectores/indicadores reales.

Por ahora, este script lanza un mensaje claro y termina.
"""
from __future__ import annotations

import sys


def main() -> None:
    print(
        "Este script aún no está implementado.\n"
        "Pertenece a la fase F3 del plan del TFG (Datos y motor).\n"
        "\n"
        "Mientras tanto, el dashboard funciona con datos sintéticos:\n"
        "    python scripts/generate_synthetic_data.py\n"
        "    streamlit run dashboard/app.py\n"
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
