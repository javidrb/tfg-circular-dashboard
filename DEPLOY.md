# Cómo desplegar el dashboard en Streamlit Community Cloud

Esta guía te lleva desde **«mi código está sólo en mi Mac»** hasta **«mi
dashboard tiene URL pública»** en aproximadamente 15 minutos.

Necesitas:
- Cuenta de **GitHub** (gratis): https://github.com/join
- Cuenta de **Streamlit Community Cloud** (gratis, con login de GitHub):
  https://share.streamlit.io

---

## Paso 1 · Limpiar el repo Git que ha quedado a medias

Mientras montaba el proyecto en mi sandbox creé un `.git/` que no se pudo
cerrar limpiamente. Hay que borrarlo antes de empezar (en tu Mac sí que
puedes borrarlo sin problema):

```bash
cd "$HOME/Desktop/TFG 26/dashboard-tfg"
rm -rf .git
ls -la       # ya no debería aparecer la carpeta .git
```

---

## Paso 2 · Inicializar Git en tu Mac

```bash
cd "$HOME/Desktop/TFG 26/dashboard-tfg"

# Configura Git por primera vez (si nunca lo has hecho en este Mac)
git config --global user.name  "Javier de Ramón Boj"
git config --global user.email "javierderamonboj@gmail.com"

# Inicializa el repo y crea la rama main
git init -b main
git add .
git status               # echa un vistazo a lo que se va a commitear
git commit -m "Primer commit: MVP del dashboard del TFG"
```

Si `git init -b main` te da un error (Git muy antiguo), usa esta variante:

```bash
git init
git checkout -b main
```

---

## Paso 3 · Crear el repositorio en GitHub

1. Entra en https://github.com/new
2. Rellena:
   - **Repository name:** `tfg-circular-dashboard` (o el nombre que prefieras)
   - **Description:** `Dashboard interactivo para escenarios de economía circular — TFG USP-CEU 2025/2026`
   - **Visibilidad:** **Public** (Streamlit Community Cloud lo necesita público; alternativa: usar Streamlit Cloud con repos privados, pero requiere activar los permisos)
   - **NO** marques «Add a README», «Add .gitignore» ni «Choose a license» — el repo ya tiene los suyos.
3. Haz clic en **«Create repository»**.
4. GitHub te muestra una página con instrucciones. Lo que nos interesa es la
   sección «push an existing repository from the command line».

---

## Paso 4 · Conectar tu repo local con GitHub y subirlo

GitHub te dará dos comandos. Sustituye `<TU-USUARIO>` por tu usuario real:

```bash
cd "$HOME/Desktop/TFG 26/dashboard-tfg"

git remote add origin https://github.com/<TU-USUARIO>/tfg-circular-dashboard.git
git branch -M main
git push -u origin main
```

La primera vez te pedirá autenticarte. Si te pide contraseña, **no uses tu
contraseña de GitHub** — usa un *Personal Access Token*:

1. Ve a https://github.com/settings/tokens?type=beta
2. **Generate new token** → fine-grained → solo permisos sobre el repo recién creado.
3. Copia el token (sólo se muestra una vez).
4. Cuando Git te pida la contraseña, pega el token.

Alternativa más cómoda a medio plazo: instala **GitHub CLI** (`brew install gh`)
y haz `gh auth login`.

Cuando termine el push, recarga la URL de tu repo en GitHub y deberías ver
todo el código.

---

## Paso 5 · Desplegar en Streamlit Community Cloud

1. Entra en https://share.streamlit.io y haz login con tu cuenta de GitHub.
2. Pulsa **«New app»** o **«Create app»**.
3. Rellena el formulario:
   - **Repository:** `<TU-USUARIO>/tfg-circular-dashboard`
   - **Branch:** `main`
   - **Main file path:** `dashboard/app.py`
   - **App URL (opcional):** elige algo memorable, p. ej. `tfg-economia-circular`.
4. Pulsa **«Deploy»**.

Streamlit Cloud hará:
- Clonar tu repo.
- Instalar Python 3.11 (lo lee de `runtime.txt`).
- Instalar `requirements.txt`.
- Lanzar `streamlit run dashboard/app.py`.
- Cuando arranque, el dashboard generará automáticamente los datos sintéticos
  si no encuentra ninguno (gracias al fallback que añadí en `data_loader.py`).

El primer arranque tarda **3–5 minutos**. Luego el deploy queda en caliente
y se relanza solo cada vez que hagas push a `main`.

---

## Paso 6 · Iterar

Cualquier cambio en tu Mac:

```bash
cd "$HOME/Desktop/TFG 26/dashboard-tfg"
git add -A
git commit -m "describe el cambio aquí"
git push
```

Streamlit Cloud detecta el push y redespliega automáticamente en ~30 segundos.

---

## Solución de problemas habituales

**`fatal: not a git repository`**
Estás fuera de la carpeta. Ejecuta `cd "$HOME/Desktop/TFG 26/dashboard-tfg"`.

**`error: failed to push some refs`**
GitHub tiene cambios que tu local no tiene (o el repo no estaba vacío).
Solución: `git pull --rebase origin main` y vuelve a empujar.

**Streamlit Cloud: «ModuleNotFoundError: dashboard»**
El path del archivo principal está mal. En el formulario, **Main file path**
tiene que ser `dashboard/app.py`, no sólo `app.py`.

**Streamlit Cloud: «No module named pyarrow»**
No es un error real: el código cae a CSV automáticamente. Si quieres evitar
el warning en logs, comenta la línea de `pyarrow` en `requirements.txt` o
fuerza una versión más reciente.

**Streamlit Cloud: deploy se queda colgado**
Mira los logs (botón «Manage app» → «Logs»). Lo más habitual es un import
fallando. Copia el error y avísame, lo depuramos.

**El repo es privado y Streamlit Cloud no lo ve**
Cuenta gratuita: ve a https://share.streamlit.io/settings/, sección
«Connect to GitHub», y autoriza acceso a repos privados. La cuenta gratuita
admite hasta cierto número de apps privadas.

---

## Resumen ultra-corto (cheat sheet)

```bash
# 1. Limpiar
cd "$HOME/Desktop/TFG 26/dashboard-tfg" && rm -rf .git

# 2. Git local
git init -b main
git add .
git commit -m "Primer commit: MVP del dashboard del TFG"

# 3. GitHub (después de crear el repo en la web)
git remote add origin https://github.com/<TU-USUARIO>/tfg-circular-dashboard.git
git push -u origin main

# 4. Streamlit Cloud
# https://share.streamlit.io → New app → main file: dashboard/app.py → Deploy
```

Cuando lo tengas en la URL pública, mándamela y echamos un ojo a que todo
renderice bien.
