# Dashboard interactivo para la simulación de escenarios de economía circular

> Trabajo de Fin de Grado · Javier de Ramón Boj · Universidad San Pablo-CEU · curso 2025/2026

Dashboard web que permite a un usuario sin perfil técnico modificar palancas de
circularidad y observar en tiempo casi real su efecto sobre el Valor Añadido, el
empleo y los principales indicadores ambientales. Construido sobre **Streamlit**
con datos generados por **pycirk** sobre **EXIOBASE 3.3.sm**.

En esta versión inicial (MVP) los escenarios se sirven desde **datos sintéticos**
que imitan la salida real de pycirk. La conexión con el motor real está prevista
para la fase F3 del plan de trabajo del TFG; al estar la capa de datos
abstraída en `dashboard/data_loader.py`, la sustitución es mecánica.

---

## Estructura del repositorio

```
dashboard-tfg/
├── dashboard/                  # Código de la aplicación Streamlit
│   ├── __init__.py
│   ├── app.py                  # Punto de entrada
│   ├── data_loader.py          # Acceso a datos (sintético / pycirk)
│   └── sensitivity.py          # Tornado plots y elasticidades
├── scripts/
│   └── generate_synthetic_data.py   # Datos sintéticos compatibles con pycirk
├── data/
│   ├── synthetic/              # Salidas del generador (Parquet + metadata.json)
│   └── pycirk_runs/            # (Vacío) Aquí caerán los datos reales
├── docs/
│   └── architecture.md
├── tests/
├── requirements.txt
├── pyproject.toml
└── README.md
```

---

## Instalación

Requiere Python 3.11 o superior.

```bash
# 1. Clonar el repositorio
git clone <url>
cd dashboard-tfg

# 2. Crear un entorno virtual y activarlo
python3.11 -m venv .venv
source .venv/bin/activate          # macOS/Linux
# .venv\Scripts\activate           # Windows

# 3. Instalar dependencias
pip install -r requirements.txt
```

---

## Uso (con datos sintéticos)

```bash
# 1. Generar el dataset sintético
python scripts/generate_synthetic_data.py

# 2. Lanzar el dashboard
streamlit run dashboard/app.py
```

La aplicación se abre en `http://localhost:8501`.

### Lo que ofrece

- **Pestaña Resumen**: KPIs (Valor Añadido, Empleo, CO₂eq, Energía) con
  variación absoluta y relativa frente al baseline, más un ranking de los
  diez sectores más afectados.
- **Pestaña Económico**: comparativa baseline vs. escenario por sector para
  Valor Añadido, Empleo y Producción, con descarga de la tabla en CSV.
- **Pestaña Ambiental**: visualización por región y top de sectores
  responsables del cambio para CO₂eq, materiales y energía.
- **Pestaña Sensibilidad**: tornado plot del top-12 de sectores por magnitud
  de impacto y tabla de elasticidades sectoriales.

### Escenarios incluidos en los datos sintéticos

| ID                              | Descripción                                          |
| ------------------------------- | ---------------------------------------------------- |
| `esc_vida_util_vehiculos_10`    | +10 % vida útil del parque automovilístico           |
| `esc_vida_util_vehiculos_50`    | +50 % vida útil (escenario disruptivo)               |
| `esc_acero_secundario_30`       | +30 % en la cuota de acero secundario / reciclaje    |
| `esc_eficiencia_energetica_20`  | +20 % de eficiencia energética en sectores intensivos |

---

## Conexión con pycirk (próximamente)

Cuando se sustituyan los datos sintéticos por los de pycirk:

1. Ejecutar `pycirk` con los YAML de escenarios (vendrán en `scripts/run_pycirk.py`).
2. Volcar los resultados en `data/pycirk_runs/` con el mismo esquema que
   `data/synthetic/all_scenarios.parquet`.
3. El dashboard los detectará automáticamente y los usará en lugar de los sintéticos.

El esquema requerido es:

```
columnas: scenario | year | analysis | region | sector | indicator | value | unit
```

---

## Decisiones de diseño

- **Single-source-of-truth en formato largo (Parquet).** Permite filtrar y
  agregar con pandas sin reestructurar; muy eficiente con `pyarrow`.
- **Capa `data_loader` aislada.** El dashboard nunca lee Parquets directamente.
  Esto facilita testear y cambiar la fuente.
- **Lógica de cálculo fuera de la UI.** `sensitivity.py` no importa Streamlit;
  se puede testear con pytest sin entorno gráfico.
- **Caché agresiva con `@st.cache_data`.** Los Parquets sólo se leen una vez por
  sesión; los filtros operan sobre la copia en memoria.

---

## Bibliografía mínima

- Donati, F. et al. (2020). *Modeling the circular economy in environmentally
  extended input-output tables: Methods, software and case study* (pycirk).
- Donati, F. et al. (2021). *Modeling the circular economy in environmentally
  extended input-output: A web application* (RaMa-Scene).
- Stadler, K. et al. (2018). *EXIOBASE 3*. Journal of Industrial Ecology.
- Miller, R. E., & Blair, P. D. (2009). *Input-Output Analysis: Foundations
  and Extensions*.
- Geissdoerfer, M. et al. (2017). *The Circular Economy – A new sustainability
  paradigm?*

Bibliografía completa en la memoria del TFG (`TFG_Memoria.docx`).

---

## Licencia

MIT (provisional). Se confirmará al cierre del TFG.
