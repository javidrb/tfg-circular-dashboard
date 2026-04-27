"""
Smoke tests: garantizan que la lógica fundamental se ejecuta sin error
después de generar el dataset sintético. No usan Streamlit.

Para ejecutar:
    python -m pytest tests/ -v
o (sin pytest):
    python tests/test_smoke.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _ensure_synthetic_data() -> None:
    syn = ROOT / "data" / "synthetic"
    # Acepta Parquet o CSV (depende de si pyarrow está instalado)
    if (syn / "all_scenarios.parquet").exists() or (syn / "all_scenarios.csv").exists():
        return
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "generate_synthetic_data.py")],
        check=True,
    )


def test_generator_produces_expected_files() -> None:
    _ensure_synthetic_data()
    syn = ROOT / "data" / "synthetic"
    assert ((syn / "baseline.parquet").exists() or (syn / "baseline.csv").exists())
    assert ((syn / "all_scenarios.parquet").exists() or (syn / "all_scenarios.csv").exists())
    assert (syn / "metadata.json").exists()
    meta = json.loads((syn / "metadata.json").read_text(encoding="utf-8"))
    assert "regions" in meta and len(meta["regions"]) > 0
    assert "sectors" in meta and len(meta["sectors"]) > 0
    assert "scenarios" in meta and len(meta["scenarios"]) >= 2  # baseline + al menos 1


def test_data_loader_returns_bundle() -> None:
    _ensure_synthetic_data()
    from dashboard.data_loader import load_all
    bundle = load_all(prefer="synthetic")
    assert bundle.source == "synthetic"
    assert len(bundle.df) > 0
    expected_cols = {"scenario", "region", "sector", "indicator", "value", "unit"}
    assert expected_cols.issubset(set(bundle.df.columns))


def test_aggregations_and_deltas() -> None:
    _ensure_synthetic_data()
    from dashboard.data_loader import (
        comparison_breakdown, delta_vs_baseline, total_indicator,
    )
    from dashboard.data_loader import load_all
    bundle = load_all(prefer="synthetic")
    sc = "esc_vida_util_vehiculos_50"
    assert total_indicator(bundle.df, "value_added", "baseline") > 0
    assert total_indicator(bundle.df, "value_added", sc) > 0
    d_abs, d_rel = delta_vs_baseline(bundle.df, "value_added", sc)
    assert isinstance(d_abs, float) and isinstance(d_rel, float)
    cmp = comparison_breakdown(bundle.df, "value_added", sc, by="sector")
    assert {"sector", "baseline", "scenario", "delta_abs", "delta_rel"}.issubset(cmp.columns)
    assert len(cmp) > 0


def test_sensitivity_module() -> None:
    _ensure_synthetic_data()
    from dashboard.data_loader import load_all
    from dashboard.sensitivity import elasticity, important_sectors, tornado_data
    bundle = load_all(prefer="synthetic")
    sc = "esc_acero_secundario_30"
    tornado = tornado_data(bundle.df, "co2eq", sc, top_n=5)
    assert len(tornado) <= 5
    assert "delta_rel" in tornado.columns

    e = elasticity(bundle.df, "value_added", "Vehículos y partes", "esc_vida_util_vehiculos_50")
    assert isinstance(e, float)

    imp = important_sectors(bundle.df, "co2eq", sc, n=3)
    assert len(imp) <= 3
    assert "share_of_change" in imp.columns


if __name__ == "__main__":
    fns = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"  ✓ {fn.__name__}")
        except AssertionError as e:  # pragma: no cover
            print(f"  ✗ {fn.__name__}: {e}")
            failed += 1
    if failed:
        print(f"\n{failed} prueba(s) fallaron"); sys.exit(1)
    print(f"\n{len(fns)} pruebas OK")
