# Arquitectura del dashboard

## Visión general

El sistema se divide en tres capas con responsabilidades claramente separadas:

```
┌─────────────────────────────────────────────────────────────────────┐
│  Capa de presentación (Streamlit)                                   │
│  · dashboard/app.py                                                 │
│  · No contiene lógica de cálculo: sólo orquesta widgets y gráficos. │
└────────────────────────────┬────────────────────────────────────────┘
                             │ usa
┌────────────────────────────▼────────────────────────────────────────┐
│  Capa de análisis (puro Python, testeable sin GUI)                  │
│  · dashboard/data_loader.py  (filtros, agregaciones, comparativas)  │
│  · dashboard/sensitivity.py  (tornado plots, elasticidades)         │
└────────────────────────────┬────────────────────────────────────────┘
                             │ lee Parquet
┌────────────────────────────▼────────────────────────────────────────┐
│  Capa de datos                                                      │
│  · data/synthetic/   ← scripts/generate_synthetic_data.py           │
│  · data/pycirk_runs/ ← scripts/run_pycirk.py (próximamente)         │
└─────────────────────────────────────────────────────────────────────┘
```

## Esquema de datos canónico

Toda la información se representa en **formato largo** (long/tidy) para que
los filtros y agregaciones de pandas sean triviales. Una sola tabla,
`all_scenarios.parquet`, contiene todos los escenarios apilados.

| Columna     | Tipo    | Descripción                                       |
|-------------|---------|---------------------------------------------------|
| `scenario`  | string  | `baseline` o ID del escenario circular            |
| `year`      | int     | Año del baseline subyacente (2011 en EXIOBASE 3)  |
| `analysis`  | string  | `hotspot` (donde ocurre) o `contribution`         |
| `region`    | string  | Región o país                                     |
| `sector`    | string  | Sector económico agregado                         |
| `indicator` | string  | `value_added`, `employment`, `output`, `co2eq`, `materials`, `energy` |
| `value`     | float   | Valor numérico                                    |
| `unit`      | string  | Unidad del indicador                              |

### Por qué formato largo

- Compatible con la salida natural de pycirk tras `melt`.
- Filtrado vectorizado eficiente (no hay que pivotar antes de filtrar).
- Permite añadir nuevas dimensiones (años, escenarios, niveles de detalle)
  sin alterar la API del dashboard.

## Decisiones clave

### 1. Datos sintéticos antes que reales
Trabajar con datos sintéticos durante F1–F2 permite:
- Iterar sobre la UX sin esperar a la instalación de EXIOBASE.
- Disponer de smoke tests en CI sin depender de descargas externas.
- Disociar problemas de presentación de problemas de modelado.

Cuando llegue F3, el cambio es transparente: el cargador busca primero en
`data/pycirk_runs/` y, si no encuentra nada, recurre a `data/synthetic/`.

### 2. Cálculo fuera de la UI
`sensitivity.py` y `data_loader.py` no importan `streamlit`. Esto permite:
- Test con `pytest` sin entorno gráfico.
- Reutilizar la lógica desde notebooks o scripts batch.
- Refactorizar la UI sin tocar la matemática.

### 3. Cacheo en dos niveles
- `@lru_cache` sobre `load_all` evita releer el Parquet en la misma sesión
  Python (útil en notebooks).
- `@st.cache_data` sobre el wrapper Streamlit evita releer entre interacciones
  del mismo usuario.

### 4. Palancas «de lectura» en el MVP
Los escenarios están pre-calculados en F1. Las palancas del sidebar muestran
los parámetros aplicados pero están deshabilitadas. En F4 (cuando se conecte
pycirk en vivo) las palancas pasarán a recalcular el escenario al vuelo.

## Roadmap de evolución

| Fase | Cambio principal                                                       |
|------|------------------------------------------------------------------------|
| F1   | MVP con datos sintéticos (este estado)                                 |
| F3   | Conexión con pycirk: `scripts/run_pycirk.py` genera Parquets reales    |
| F4   | Palancas activas: cada interacción dispara un recálculo de pycirk     |
| F5   | Caso de estudio (parque UE-27) y test de usabilidad SUS                |
| F6   | Despliegue en Streamlit Community Cloud y memoria final                |

## Tests

Los tests se ubican en `tests/`. Alcance previsto:
- `tests/test_data_loader.py`: filtros, agregaciones, deltas.
- `tests/test_sensitivity.py`: tornado, elasticidad, sectores importantes.
- `tests/test_synthetic.py`: que el generador produce un esquema válido y
  reproducible (mismo seed → mismos valores).
