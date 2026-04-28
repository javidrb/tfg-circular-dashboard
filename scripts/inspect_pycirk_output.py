"""
Inspecciona la estructura del data.pkl que produce pycirk -od True.

Uso:
    python scripts/inspect_pycirk_output.py [ruta]

Si no se pasa ruta, busca automáticamente el data.pkl más reciente
dentro de ~/Documents/pycirk/.
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import pandas as pd


def find_latest_pkl() -> Path | None:
    base = Path.home() / "Documents" / "pycirk"
    if not base.exists():
        return None
    candidates = sorted(base.rglob("data.pkl"), key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def describe_dataframe(df: pd.DataFrame, indent: str = "  ") -> None:
    print(f"{indent}shape={df.shape}")
    print(f"{indent}columns ({len(df.columns)}): {list(df.columns)[:8]}{'...' if len(df.columns) > 8 else ''}")
    print(f"{indent}index names: {df.index.names}")
    print(f"{indent}index sample:")
    for i in df.index[:3]:
        print(f"{indent}  {i}")
    print(f"{indent}head:")
    try:
        print(df.head(3).to_string().replace("\n", "\n" + indent + "  "))
    except Exception as e:
        print(f"{indent}  (error mostrando head: {e})")


def main() -> None:
    if len(sys.argv) > 1:
        p = Path(sys.argv[1]).expanduser()
    else:
        p = find_latest_pkl()
        if p is None:
            print("No se encontró ningún data.pkl en ~/Documents/pycirk/.")
            print("Pasa la ruta como argumento.")
            sys.exit(1)

    print(f"=== Inspeccionando ===")
    print(f"Ruta:    {p}")
    print(f"Tamaño:  {p.stat().st_size / 1024:.1f} KB")
    print()

    with open(p, "rb") as f:
        obj = pickle.load(f)

    print(f"Tipo raíz: {type(obj).__name__}")
    print()

    if isinstance(obj, pd.DataFrame):
        print("Es un DataFrame.")
        describe_dataframe(obj)
    elif isinstance(obj, pd.Series):
        print(f"Es una Series. len={len(obj)}")
        print(obj.head(10).to_string())
    elif isinstance(obj, dict):
        print(f"Es un dict con {len(obj)} clave(s):")
        for k, v in obj.items():
            print(f"  {k!r}: {type(v).__name__}")
            if isinstance(v, pd.DataFrame):
                print(f"    shape={v.shape}")
                if len(v) > 0:
                    print(f"    index sample: {list(v.index[:2])}")
                    print(f"    columns: {list(v.columns)[:6]}{'...' if len(v.columns) > 6 else ''}")
            elif hasattr(v, "__len__"):
                try:
                    print(f"    len={len(v)}")
                except Exception:
                    pass
    elif isinstance(obj, (list, tuple)):
        print(f"Es una secuencia con {len(obj)} elementos.")
        for i, v in enumerate(obj[:5]):
            print(f"  [{i}] {type(v).__name__}", end="")
            if isinstance(v, pd.DataFrame):
                print(f"  shape={v.shape}")
            else:
                print()
    else:
        attrs = [a for a in dir(obj) if not a.startswith("_")]
        print(f"Tipo desconocido. Atributos relevantes: {attrs[:20]}")


if __name__ == "__main__":
    main()
