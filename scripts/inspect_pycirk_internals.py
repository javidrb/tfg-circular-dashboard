"""
Inspecciona el código fuente de pycirk para entender qué espera la validación
del «penetration coefficient» y cómo procesa las filas de scenarios.xlsx.

Uso (en conda env pycirk):
    python scripts/inspect_pycirk_internals.py
"""
from __future__ import annotations

import inspect
import textwrap
from pathlib import Path

import pycirk

pycirk_dir = Path(pycirk.__file__).parent
print(f"=== pycirk instalado en: {pycirk_dir}\n")

target = pycirk_dir / "make_scenarios.py"
print(f"=== {target.name} ===\n")
text = target.read_text(encoding="utf-8")
lines = text.splitlines()

# Imprime las 50 líneas alrededor de basic_mult y counterfactual_engine
for keyword in ("def basic_mult", "def counterfactual_engine", "def make_new",
                "def counterfactual"):
    for i, ln in enumerate(lines):
        if ln.lstrip().startswith(keyword):
            start = max(0, i - 2)
            end = min(len(lines), i + 60)
            print(f"\n--- {keyword} (líneas {start+1}-{end}) ---")
            for j in range(start, end):
                print(f"{j+1:4d}  {lines[j]}")
            break

print("\n\n=== Estructura esperada de filas según el código ===")
print("Si ves dict accesses tipo int1['kt'], int1['kp'], int1['cat_o'], etc.")
print("son las columnas que pycirk espera en cada fila.")
