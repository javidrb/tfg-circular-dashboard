"""
Sobrescribe scenario_2 y scenario_3 del scenarios.xlsx de pycirk con dos
escenarios circulares de verdad (con compensación primary + ancillary).

scenario_2: «Boost acero secundario»
    Sustitución del acero primario por acero secundario en los tres mayores
    consumidores (vehículos, construcción, maquinaria), más reducción de la
    intensidad de CO₂ del acero primario residual.

scenario_3: «Vida útil del parque automovilístico EU +50 %»
    Reducción de la demanda final de vehículos en la UE compensada con
    servicios de reparación, y reducción de inputs primarios (acero y
    aluminio) en la fabricación de vehículos también compensados con
    servicios técnicos.

Uso (desde el conda env pycirk):
    python scripts/build_circular_scenarios.py
    pycirk -tm 0 -dr "" -ag 1 -ms True -sc 2 -s True -od True
    pycirk -tm 0 -dr "" -ag 1 -ms True -sc 3 -s True -od True
    python scripts/convert_pycirk_output.py
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import openpyxl

SCENARIOS_PATH = Path.home() / "Documents" / "pycirk" / "scenarios.xlsx"


# --------------------------------------------------------------------------- #
# Búsqueda flexible de códigos en la hoja names_categories
# --------------------------------------------------------------------------- #

def load_codes(wb: openpyxl.Workbook,
               only_categories: tuple[str, ...] = ("Products",)) -> dict[str, str]:
    """
    Devuelve un dict {nombre_largo_lowercase: código} a partir de la hoja
    names_categories, filtrado por categoría.

    Por defecto sólo devuelve Productos para evitar falsos positivos con
    extensiones ambientales y emisiones que pueden contener palabras como
    «primary» o «aluminium» en su descripción.
    """
    if "names_categories" not in wb.sheetnames:
        sys.exit("ERROR: la hoja 'names_categories' no existe en scenarios.xlsx.")
    ws = wb["names_categories"]
    codes: dict[str, str] = {}
    cats_low = tuple(c.lower() for c in only_categories)
    for r in range(2, ws.max_row + 1):
        cat = ws.cell(r, 1).value
        name = ws.cell(r, 2).value
        code = ws.cell(r, 3).value
        if cat is None or name is None or code is None:
            continue
        if str(cat).strip().lower() not in cats_low:
            continue
        key = str(name).strip().lower()
        codes[key] = str(code).strip()
    return codes


def find_code(codes: dict[str, str], *needles: str,
              exclude: tuple[str, ...] = ()) -> str:
    """
    Devuelve el primer código cuyo nombre contiene TODOS los needles y NINGUNO
    de los exclude. Lanza error si no encuentra nada.
    """
    needles_low = [n.lower() for n in needles]
    excludes_low = [e.lower() for e in exclude]
    matches = []
    for name, code in codes.items():
        if not all(k in name for k in needles_low):
            continue
        if any(e in name for e in excludes_low):
            continue
        matches.append((name, code))
    if not matches:
        sys.exit(f"ERROR: no encuentro código que contenga {needles} (excluyendo {exclude}).")
    if len(matches) > 1:
        names = ", ".join(f"'{n}' ({c})" for n, c in matches[:3])
        print(f"  [info] {needles} matchea {len(matches)} códigos, uso el primero: {matches[0][1]}")
        print(f"         candidatos: {names}{'...' if len(matches) > 3 else ''}")
    return matches[0][1]


# --------------------------------------------------------------------------- #
# Escritura de escenarios
# --------------------------------------------------------------------------- #

HEADER_ROW1 = [
    None, None, None,
    "Reg\nCoordinates \n(o=origin or row, d=destination or column)", None,
    "Prod/sect\nCoordinates", None,
    "kt technical change coefficients % \n( - means reduction)", None,
    "at absolute technical change ( - reduction, + increase)", None,
]
HEADER_ROW2 = [
    "matrix", "identifier", "change_type",
    "reg_o", "reg_d",
    "cat_o", "cat_d",
    "kt1", "kt2",
    "at1", "at2",
]


def _cell_is_merged(ws, row: int, col: int) -> bool:
    """Devuelve True si (row, col) está dentro de un rango combinado."""
    for mr in ws.merged_cells.ranges:
        if mr.min_row <= row <= mr.max_row and mr.min_col <= col <= mr.max_col:
            return True
    return False


def clear_sheet(ws) -> None:
    """
    Borra todas las filas de datos (de la 3 en adelante), preservando las dos
    filas de cabecera (que pycirk crea con celdas combinadas y no se pueden
    sobreescribir desde openpyxl).
    """
    max_r = ws.max_row
    max_c = max(ws.max_column, len(HEADER_ROW2))
    for r in range(3, max_r + 1):
        for c in range(1, max_c + 1):
            if _cell_is_merged(ws, r, c):
                continue
            ws.cell(r, c).value = None


def write_intervention(ws, row: int, *, matrix: str, identifier, change_type: str,
                       reg_o: str = "All", reg_d: str = "All",
                       cat_o: str, cat_d: str,
                       kt1=None, kt2=None, at1=None, at2=None,
                       kp1: float | None = 100, kp2: float | None = None,
                       sub=None, copy=None) -> None:
    """
    Escribe una fila siguiendo el esquema completo de scenarios.xlsx (25 columnas).

    Por defecto kp1=100 (100 % de penetración del cambio técnico). Esto es
    imprescindible: pycirk lanza «specify penetration coefficient» si kt1
    está definido pero kp1 está vacío. Donati lo confirma en su scenario_1.
    """
    # Mapeo posicional: columna → valor. Sólo escribimos las que nos importan.
    cells = {
        1: matrix, 2: identifier, 3: change_type,
        4: reg_o, 5: reg_d, 6: cat_o, 7: cat_d,
        8: kt1, 9: kt2,
        10: at1, 11: at2,
        12: kp1, 13: kp2,
        14: sub, 15: copy,
    }
    for col, val in cells.items():
        if _cell_is_merged(ws, row, col):
            continue
        ws.cell(row, col).value = val


# --------------------------------------------------------------------------- #
# Definición de los dos escenarios
# --------------------------------------------------------------------------- #

def build_scenario_2(ws, codes: dict[str, str]) -> None:
    """
    «Boost acero secundario»: -X % acero primario, +X % acero secundario,
    en vehículos / construcción / maquinaria, más mejora de intensidad CO2
    del acero primario.
    """
    clear_sheet(ws)

    motor_vehicles    = find_code(codes, "motor vehicles", "trailers")
    # C_TDMO: "Sale, maintenance, repair of motor vehicles..."
    sale_maint_motor  = find_code(codes, "maintenance", "motor vehicles")
    # C_TDRT: "Retail trade services... repair services of personal and household goods"
    retail_repair     = find_code(codes, "retail", "repair services")
    # C_ELMA: electrical machinery
    elec_machinery    = find_code(codes, "electrical machinery")
    # C_MACH: Machinery and equipment n.e.c.
    machinery         = find_code(codes, "machinery and equipment",
                                   exclude=("fabricated", "renting", "office", "electrical"))

    # Estrategia: modificaciones EN LA MATRIZ Y (demanda final). Esto inyecta
    # crecimiento neto en los sectores ancillary, garantizando ganadores visibles.
    # Patrón: los consumidores compran menos «cosas nuevas» y más «servicios».
    # Magnitudes grandes (±35%) para que los efectos sean nítidos en el dashboard.
    interventions = [
        # ID 1: De motor vehicles nuevos → servicios de mantenimiento/reparación de motor
        ("Y", 1, "Primary",   motor_vehicles,    "All", -35),
        ("Y", 1, "Ancillary", sale_maint_motor,  "All", +35),

        # ID 2: De maquinaria eléctrica nueva → servicios de retail + repair
        ("Y", 2, "Primary",   elec_machinery,    "All", -30),
        ("Y", 2, "Ancillary", retail_repair,     "All", +30),

        # ID 3: De maquinaria nueva → servicios de retail + repair
        ("Y", 3, "Primary",   machinery,         "All", -25),
        ("Y", 3, "Ancillary", retail_repair,     "All", +25),
    ]
    row = 3
    for matrix, ident, kind, cat_o, cat_d, kt1 in interventions:
        write_intervention(ws, row, matrix=matrix, identifier=ident,
                           change_type=kind, cat_o=cat_o, cat_d=cat_d, kt1=kt1)
        row += 1

    print(f"  scenario_2 -> 6 intervenciones Y (3 pares Primary+Ancillary):")
    print(f"     motor_vehicles    = {motor_vehicles}")
    print(f"     sale_maint_motor  = {sale_maint_motor}")
    print(f"     elec_machinery    = {elec_machinery}")
    print(f"     machinery         = {machinery}")
    print(f"     retail_repair     = {retail_repair}")


def build_scenario_3(ws, codes: dict[str, str]) -> None:
    """
    «Vida útil parque automovilístico EU +50 %»:
    Reduce demanda final de vehículos en EU, compensada con servicios técnicos.
    Reduce inputs primarios (acero, aluminio) en fabricación de vehículos,
    compensados con servicios de reparación.
    """
    clear_sheet(ws)

    motor_vehicles    = find_code(codes, "motor vehicles", "trailers")
    sale_maint_motor  = find_code(codes, "maintenance", "motor vehicles")
    retail_repair     = find_code(codes, "retail", "repair services")
    elec_machinery    = find_code(codes, "electrical machinery")
    machinery         = find_code(codes, "machinery and equipment",
                                   exclude=("fabricated", "renting", "office", "electrical"))

    # Estrategia: modificaciones Y exclusivamente, restringidas a EU.
    # Magnitudes grandes (±40-45%) para mostrar el efecto disruptivo de una
    # transición circular agresiva al servicio.
    interventions = [
        # ID 1: EU compra -45% motor vehicles, +45% servicios de reparación de motor
        ("Y", 1, "Primary",   "EU", "EU", motor_vehicles,   "All", -45),
        ("Y", 1, "Ancillary", "EU", "EU", sale_maint_motor, "All", +45),

        # ID 2: EU compra -35% maquinaria eléctrica, +35% retail + repair
        ("Y", 2, "Primary",   "EU", "EU", elec_machinery,   "All", -35),
        ("Y", 2, "Ancillary", "EU", "EU", retail_repair,    "All", +35),

        # ID 3: EU compra -30% maquinaria, +30% retail + repair
        ("Y", 3, "Primary",   "EU", "EU", machinery,        "All", -30),
        ("Y", 3, "Ancillary", "EU", "EU", retail_repair,    "All", +30),
    ]
    row = 3
    for matrix, ident, kind, reg_o, reg_d, cat_o, cat_d, kt1 in interventions:
        write_intervention(ws, row, matrix=matrix, identifier=ident, change_type=kind,
                           reg_o=reg_o, reg_d=reg_d, cat_o=cat_o, cat_d=cat_d, kt1=kt1)
        row += 1

    print(f"  scenario_3 -> 6 intervenciones Y restringidas a EU:")
    print(f"     motor_vehicles    = {motor_vehicles}")
    print(f"     sale_maint_motor  = {sale_maint_motor}")
    print(f"     elec_machinery    = {elec_machinery}")
    print(f"     machinery         = {machinery}")
    print(f"     retail_repair     = {retail_repair}")


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #

def main() -> None:
    if not SCENARIOS_PATH.exists():
        sys.exit(
            f"ERROR: no encuentro {SCENARIOS_PATH}. "
            "Ejecuta primero `pycirk -tm 0 -dr \"\" -ag 1 -ms True -sc 0 -s False -od False` "
            "para que pycirk genere el archivo."
        )

    # Backup
    backup = SCENARIOS_PATH.with_suffix(".xlsx.bak")
    shutil.copy(SCENARIOS_PATH, backup)
    print(f"Backup creado: {backup}")

    print(f"Abriendo: {SCENARIOS_PATH}")
    wb = openpyxl.load_workbook(SCENARIOS_PATH)
    codes = load_codes(wb)
    print(f"  {len(codes)} códigos disponibles en names_categories")

    if "scenario_2" not in wb.sheetnames or "scenario_3" not in wb.sheetnames:
        sys.exit("ERROR: scenarios.xlsx no contiene scenario_2 y scenario_3.")

    print("\nReescribiendo scenario_2 (Boost acero secundario):")
    build_scenario_2(wb["scenario_2"], codes)

    print("\nReescribiendo scenario_3 (Vida útil vehículos EU +50 %):")
    build_scenario_3(wb["scenario_3"], codes)

    wb.save(SCENARIOS_PATH)
    print(f"\nGuardado: {SCENARIOS_PATH}")
    print("\nSiguiente paso (en el conda env pycirk):")
    print("  pycirk -tm 0 -dr \"\" -ag 1 -ms True -sc 2 -s True -od True")
    print("  pycirk -tm 0 -dr \"\" -ag 1 -ms True -sc 3 -s True -od True")
    print("\nLuego:")
    print("  python scripts/convert_pycirk_output.py")


if __name__ == "__main__":
    main()
