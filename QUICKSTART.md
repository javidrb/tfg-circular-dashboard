# Quickstart — Cómo arrancar el dashboard del TFG en tu máquina

Esta guía es la versión rápida del README, pensada para que tengas algo
funcionando en tu portátil en menos de 10 minutos.

---

## 0. Antes de empezar

Necesitas tener instalado:

- **Python 3.11 o superior**
  - Comprueba en una terminal: `python3 --version`
  - Si tienes 3.10 o más antiguo, descarga la 3.11 desde python.org.
- **Git** (no imprescindible si usas la carpeta directamente desde `Desktop/TFG 26/dashboard-tfg`).

Tu carpeta de trabajo es:

```
~/Desktop/TFG 26/dashboard-tfg
```

---

## 1. Abrir una terminal y posicionarse en la carpeta

En macOS:

```bash
cd "$HOME/Desktop/TFG 26/dashboard-tfg"
pwd     # debe imprimir la ruta de arriba
ls      # deberías ver: dashboard/, scripts/, data/, README.md, requirements.txt, ...
```

Si la ruta tiene espacios, mantén las comillas alrededor.

---

## 2. Crear un entorno virtual aislado

Esto evita que las dependencias del TFG se mezclen con otras de tu sistema.

```bash
python3 -m venv .venv
source .venv/bin/activate          # macOS / Linux
# .venv\Scripts\activate           # Windows PowerShell
```

Cuando esté activo, verás `(.venv)` al principio del prompt.
Para salir: `deactivate`.

---

## 3. Instalar las dependencias

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

Si la instalación de `pyarrow` falla en tu Mac (es habitual con compiladores
viejos), no pasa nada: el proyecto cae automáticamente a CSV. Funciona igual,
sólo es algo más lento al cargar.

---

## 4. Generar el dataset sintético (1ª vez)

```bash
python scripts/generate_synthetic_data.py
```

Salida esperada:

```
Generando datos sintéticos en .../data/synthetic
  ✓ baseline.parquet (1,440 filas)
  ✓ esc_vida_util_vehiculos_10.parquet
  ✓ esc_vida_util_vehiculos_50.parquet
  ✓ esc_acero_secundario_30.parquet
  ✓ esc_eficiencia_energetica_20.parquet
  ✓ all_scenarios.parquet (7,200 filas)
  ✓ metadata.json
```

---

## 5. Lanzar el dashboard

```bash
streamlit run dashboard/app.py
```

Streamlit abre automáticamente tu navegador en `http://localhost:8501`.
Si no lo hace, copia esa URL en el navegador.

Para parar el servidor: `Ctrl + C` en la terminal.

---

## 6. (Opcional) Ejecutar los smoke tests

Para confirmar que toda la lógica está sana sin abrir el navegador:

```bash
python tests/test_smoke.py
```

Salida esperada:

```
  ✓ test_generator_produces_expected_files
  ✓ test_data_loader_returns_bundle
  ✓ test_aggregations_and_deltas
  ✓ test_sensitivity_module

4 pruebas OK
```

---

## 7. Cheat sheet de comandos

```bash
# Activar el entorno (cada vez que abres una terminal nueva)
cd "$HOME/Desktop/TFG 26/dashboard-tfg" && source .venv/bin/activate

# Regenerar los datos sintéticos
python scripts/generate_synthetic_data.py

# Lanzar el dashboard
streamlit run dashboard/app.py

# Ejecutar los tests
python tests/test_smoke.py

# Salir del entorno
deactivate
```

---

## ¿Qué viene después?

1. **Cuando tengas tutor asignado**, enséñale el dashboard funcionando con
   datos sintéticos. Es la mejor forma de alinear expectativas: el motor real
   (pycirk) sólo cambia la fuente de datos; la UI ya está cerrada.
2. **Cuando estés listo para conectar pycirk**, mira `scripts/run_pycirk.py`
   y la sección «Conexión con pycirk» del README.
3. **Cuando el tutor quiera ver la memoria**, tienes dos archivos en
   `~/Desktop/TFG 26/`:
   - `Plan_TFG_Dashboard_Economia_Circular.docx` — plan de trabajo.
   - `TFG_Memoria.docx` — borrador de la memoria con capítulos 1–4 redactados.

---

## Solución de problemas

**`command not found: python3`** → instala Python 3.11 desde python.org.

**`pip` no instala `pyarrow`** → ignora el error; el proyecto funciona con CSV.

**Streamlit no abre el navegador** → abre tú `http://localhost:8501`.

**`ModuleNotFoundError: dashboard`** → asegúrate de estar en la carpeta
`dashboard-tfg/` cuando lanzas `streamlit run dashboard/app.py`. Streamlit
añade el directorio actual al `sys.path`.

**El dashboard muestra «No se encontraron datos»** → ejecuta primero
`python scripts/generate_synthetic_data.py`.

**Cualquier otra cosa** → cuéntame el error exacto y lo depuramos.
