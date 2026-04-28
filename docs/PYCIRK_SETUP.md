# Conexión con pycirk + EXIOBASE 3.3 (Fase F3 del plan del TFG)

Esta guía sustituye los datos sintéticos del MVP por datos reales generados
por **pycirk** sobre **EXIOBASE 3.3**. Es el paso más arriesgado del TFG; ve
sin prisa y guarda el progreso después de cada bloque verde.

## Tiempo y requisitos

| Recurso | Mínimo |
|---|---|
| Tiempo total | 1–2 horas (más espera de descargas) |
| Espacio en disco | ~1 GB libres |
| RAM | 8 GB cómodos; 4 GB justo |
| Conexión | banda ancha (la base bi-regional son ~150 MB; la completa ~1 GB) |
| Python | 3.10–3.11 (pycirk no garantiza 3.12) |

> **Cuándo NO seguir esta guía aún.** Si todavía no has visto correr el
> dashboard con datos sintéticos, vuelve atrás y léete primero
> `QUICKSTART.md`. Esta guía asume que el MVP funciona.

---

## 1 · Crear un entorno virtual dedicado

pycirk arrastra dependencias antiguas que pueden chocar con el resto. Usa
un venv independiente.

```bash
cd "$HOME/Desktop/TFG 26/dashboard-tfg"
python3.11 -m venv .venv-pycirk
source .venv-pycirk/bin/activate
pip install --upgrade pip
```

> Si `python3.11` no existe en tu Mac, descárgalo de python.org. pycirk no
> juega bien con la 3.12 todavía.

---

## 2 · Instalar pycirk

Ruta canónica (PyPI):

```bash
pip install pycirk
```

Si falla la instalación (suele pasar con `numpy`/`pandas` muy nuevos),
prueba la versión congelada del Donati 2020:

```bash
pip install "pycirk==1.5.5" "numpy<2.0" "pandas<2.0"
```

Ruta alternativa (desde GitHub, último commit):

```bash
pip install git+https://github.com/CMLPlatform/pycirk.git
```

Comprueba que el ejecutable está en el PATH:

```bash
pycirk --help
```

---

## 3 · Descargar EXIOBASE 3.3

EXIOBASE 3.3.sm está publicada en Zenodo. La ruta exacta puede cambiar:

- DOI principal pycirk: https://doi.org/10.5281/zenodo.4695823
- Comprueba siempre la última versión activa.

**Opciones de tamaño:**

- **Bi-regional (recomendado para empezar):** ~150 MB. Solo distingue
  «UE-27» vs «Resto del mundo». Suficiente para los dos primeros
  escenarios y para defender la herramienta.
- **Multi-regional completa (49 regiones):** ~1 GB descomprimida.
  Necesaria si tu caso de estudio requiere desagregar países.

Descarga el ZIP, descomprímelo y mueve el contenido a la carpeta `data/`
del paquete pycirk:

```bash
# Localiza la carpeta donde pycirk vive
python -c "import pycirk, os; print(os.path.join(os.path.dirname(pycirk.__file__), 'data'))"
# Ejemplo de salida: /.../site-packages/pycirk/data
```

Mueve los archivos descomprimidos a esa carpeta. La estructura final tiene
que parecerse a:

```
.../site-packages/pycirk/data/
├── EXIOBASE_v3.3_2011_pxp_ITA_TC.npz   (o similar)
├── scenarios.xlsx                       (lo creará pycirk en el primer arranque)
└── ...
```

---

## 4 · Inicializar pycirk (genera `scenarios.xlsx`)

```bash
pycirk
```

La primera ejecución crea `scenarios.xlsx` en la carpeta `data/` con un
escenario baseline vacío. **Cierra pycirk con Ctrl+C** cuando termine la
inicialización (no necesitamos correr nada todavía).

---

## 5 · Definir nuestros 4 escenarios

Tienes una **plantilla de referencia** generada por nosotros que documenta
las intervenciones de los cuatro escenarios del MVP:

```bash
python scripts/build_scenarios_template.py
# Salida: docs/scenarios_reference.xlsx
open docs/scenarios_reference.xlsx
```

Esa plantilla **no es el archivo de pycirk**, es una referencia legible.
Tu trabajo es traducir cada fila de `interventions` al formato concreto de
`scenarios.xlsx` que pycirk espera. La estructura de `scenarios.xlsx` es:

| scenario_id | intervention_id | matrix | kind | ... |
|-------------|-----------------|--------|------|-----|
| 1 | 1 | Y | demand_change | ... |
| 1 | 2 | Y | demand_change | ... |
| ... | ... | ... | ... | ... |

Las columnas exactas dependen de tu versión de pycirk. Abre el
`scenarios.xlsx` recién creado en su carpeta `data/` y completa una hoja
por escenario, copiando filas de la plantilla.

> **Atajo si la versión de pycirk es la 1.5.x:** los nombres de productos y
> sectores deben coincidir EXACTAMENTE con la clasificación de EXIOBASE.
> En la primera fila del scenarios.xlsx oficial verás los códigos válidos.

---

## 6 · Ejecutar pycirk para todos los escenarios

```bash
pycirk -tm 0 -dr "" -ag 1 -sc "all" -s True -od True
```

Significado de los flags:

- `-tm 0` → product-by-product, asunción industry-technology (la
  recomendada por Donati et al., 2021).
- `-dr ""` → usa el directorio por defecto (`pycirk/data/`).
- `-ag 1` → bi-regional (rápido). Cambia a `-ag 0` cuando tengas la
  multi-regional completa.
- `-sc "all"` → ejecuta los cinco escenarios (baseline + 4).
- `-s True` → guarda los resultados en disco.
- `-od True` → produce el dataset agregado.

Cada escenario tarda **2–10 minutos** (bi-regional) o **15–40 minutos**
(multi-regional) según tu Mac.

---

## 7 · Convertir las salidas al esquema del dashboard

```bash
cd "$HOME/Desktop/TFG 26/dashboard-tfg"
python scripts/run_pycirk.py --skip-run --aggregation bi-regional
```

`--skip-run` evita relanzar pycirk; sólo parsea sus salidas y las vuelca a
`data/pycirk_runs/` con el esquema canónico del dashboard.

Si todo va bien verás algo como:

```
<< baseline ← scenario_0_xxxx.csv (XX,XXX filas → baseline.parquet)
<< esc_vida_util_vehiculos_10 ← ... 
...
Consolidado: XXX,XXX filas → data/pycirk_runs/all_scenarios.parquet
```

---

## 8 · Lanzar el dashboard con datos reales

```bash
cd "$HOME/Desktop/TFG 26/dashboard-tfg"
source .venv/bin/activate                # tu venv habitual, no el de pycirk
streamlit run dashboard/app.py
```

El cargador detectará `data/pycirk_runs/` automáticamente y lo usará en
lugar de los datos sintéticos. En la pestaña «Acerca de» verás
`source: pycirk` en lugar de `synthetic`.

---

## 9 · Subir los datos reales a Streamlit Cloud (opcional)

Los datos de pycirk pueden ser grandes (decenas de MB). Tres opciones:

1. **Bi-regional**: cabe en GitHub sin problema. Commitéalos.
2. **Multi-regional**: usa Git LFS o súbelos a una URL externa (Zenodo,
   Figshare) y haz que el dashboard los descargue al arrancar.
3. **Solo local**: deja el dashboard de Streamlit Cloud con datos
   sintéticos y reserva los datos reales para tu máquina (defensas, demos
   en vivo).

---

## Solución de problemas

**`pycirk: command not found` después de instalar**
Activa el venv: `source .venv-pycirk/bin/activate`. Si ya está activo,
prueba `python -m pycirk -tm 0 ...` en lugar del ejecutable.

**`ModuleNotFoundError: numpy.core._multiarray_umath`**
Tu numpy es demasiado nuevo para pycirk. Fuerza una versión compatible:
`pip install "numpy<2.0"`.

**pycirk se cuelga al cargar EXIOBASE**
Probablemente te falta un archivo. Vuelve al paso 3 y verifica que
`pycirk/data/` contiene los `.npz` esperados.

**`run_pycirk.py` no encuentra la salida**
pycirk guarda con nombres distintos según la versión. Mira en
`<sitepackages>/pycirk/data/` qué archivos `.csv` o `.h5` se crearon y
ajusta `_find_pycirk_output()` en `scripts/run_pycirk.py` si hace falta.

**El dashboard sigue mostrando los sintéticos**
El cargador prefiere `data/pycirk_runs/` sobre `data/synthetic/`. Si lo
ves al revés, comprueba que existe `data/pycirk_runs/all_scenarios.parquet`
(o `.csv`) y que `metadata.json` está presente. Borra el cache de Streamlit:
`rm -rf .streamlit/cache` o usa el botón «Clear cache» en la app.

**Indicadores con nombres distintos a los esperados**
Edita `INDICATOR_MAP` al inicio de `scripts/run_pycirk.py` añadiendo el
nombre exacto que aparece en tu salida.

---

## Si te quedas atascado

Pásame el mensaje exacto del error o el comando que ha fallado y lo
depuramos. La parte de pycirk es la que más fricción suele dar; cuenta con
una iteración o dos de ajuste fino sobre `INDICATOR_MAP` y la convención
de nombres.
