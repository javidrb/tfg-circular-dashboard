#!/usr/bin/env bash
# Lanzador one-shot del dashboard del TFG.
# Crea entorno virtual si no existe, instala dependencias, genera los datos
# sintéticos si faltan, y arranca Streamlit.
#
# Uso (desde la carpeta dashboard-tfg/):
#   bash launch.sh
# o, una vez con permisos de ejecución:
#   ./launch.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Detectar python
if command -v python3.11 >/dev/null 2>&1; then PY=python3.11
elif command -v python3 >/dev/null 2>&1;  then PY=python3
else
  echo "ERROR: no he encontrado python3 ni python3.11 en el PATH."
  echo "       Instala Python 3.11+ desde https://www.python.org/downloads/"
  exit 1
fi
echo ">> Usando $($PY --version) en $(command -v $PY)"

# Crear venv si no existe
if [ ! -d ".venv" ]; then
  echo ">> Creando entorno virtual en .venv/"
  $PY -m venv .venv
fi

# Activar venv
# shellcheck disable=SC1091
source .venv/bin/activate
echo ">> Entorno activo: $(which python)"

# Instalar dependencias (idempotente)
echo ">> Instalando dependencias…"
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet

# Generar datos sintéticos si faltan
if [ ! -f "data/synthetic/all_scenarios.parquet" ] && [ ! -f "data/synthetic/all_scenarios.csv" ]; then
  echo ">> Generando datos sintéticos…"
  python scripts/generate_synthetic_data.py
else
  echo ">> Datos sintéticos ya presentes (se reutilizan)."
fi

# Lanzar Streamlit
echo ">> Lanzando Streamlit en http://localhost:8501 (Ctrl+C para parar)"
exec streamlit run dashboard/app.py
