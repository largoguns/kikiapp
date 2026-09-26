# Kiki App

Aplicación web ligera para registrar y analizar **encuentros (Kiki)**,
**desencuentros (No Kiki)** y el **período menstrual (Marea)**, con un
dashboard completo de escritorio y una PWA móvil pensada para apuntar un
registro en tres toques.

Todo vive en un único contenedor: FastAPI sirve la API y las dos vistas, los
datos se guardan en SQLite dentro de un volumen, y —opcionalmente— se
sincronizan en ambos sentidos con una hoja de Google Sheets.

---

## Índice

- [Puesta en marcha](#puesta-en-marcha)
- [Configuración](#configuración)
- [Sincronización con Google Sheets](#sincronización-con-google-sheets)
- [Las dos vistas](#las-dos-vistas)
- [API REST](#api-rest)
- [Modelo de datos](#modelo-de-datos)
- [Desarrollo](#desarrollo)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Decisiones de diseño](#decisiones-de-diseño)

---

## Puesta en marcha

### Con Docker (recomendado)

```bash
git clone https://github.com/largoguns/kikiapp.git
cd kikiapp
docker compose up -d --build
```

La app queda en **http://localhost:8080**. Los datos persisten en el volumen
`kiki_data`, así que sobreviven a `docker compose down` y a las
reconstrucciones de la imagen.

### En Portainer

1. **Stacks → Add stack → Repository**.
2. URL del repositorio: `https://github.com/largoguns/kikiapp.git`, ruta del
   compose: `docker-compose.yml`.
3. Ajusta las variables de entorno en la sección *Environment variables*
   (ver [Configuración](#configuración)).
4. **Deploy the stack**.

Para activar la sincronización con Google Sheets hace falta, además, que el
fichero `credentials.json` exista en el host antes de levantar el stack y
descomentar su línea en `docker-compose.yml`.

### En local, sin Docker

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

DATA_DIR=./data SYNC_ENABLED=false \
  .venv/bin/python -m uvicorn app.main:app --reload --port 8080
```

¿Quieres verlo con contenido antes de meter datos reales?

```bash
DATA_DIR=./data .venv/bin/python tools/seed.py --meses 24 --reset
```

---

## Configuración

Todo se controla por variables de entorno; todas tienen valor por defecto.
Hay una plantilla en [`.env.example`](.env.example).

| Variable | Por defecto | Para qué sirve |
| :--- | :--- | :--- |
| `PORT` | `8080` | Puerto de escucha. |
| `TZ` | `Europe/Madrid` | Zona horaria con la que se calcula "hoy" (y por tanto los días sin Kiki). |
| `DATA_DIR` | `/app/data` | Carpeta del volumen donde vive `kiki.db`. |
| `DB_PATH` | `$DATA_DIR/kiki.db` | Ruta explícita de la base de datos. |
| `SYNC_ENABLED` | `true` | Interruptor general de la sincronización con Sheets. |
| `GOOGLE_SHEETS_CREDENTIALS_FILE` | `/app/credentials.json` | JSON de la Cuenta de Servicio. |
| `GOOGLE_SHEET_NAME` | `Kiki` | Nombre del documento en Drive. |
| `GOOGLE_SHEET_ID` | — | Id del documento. Si se informa, tiene prioridad sobre el nombre. |
| `GOOGLE_WORKSHEET_NAME` | `Kikis` | Pestaña dentro del documento. Si no existe, se usa la primera. |
| `SYNC_ON_STARTUP` | `true` | Sincroniza al arrancar el contenedor. |
| `SYNC_INTERVAL_MINUTES` | `360` | Cada cuánto se repite la sincronización periódica. |
| `SYNC_PUSH_DEBOUNCE_SECONDS` | `5` | Espera antes de exportar tras una escritura, para agrupar ráfagas. |

**Sin credenciales la app funciona con normalidad**: se queda en modo local,
lo dice en la cabecera del dashboard y no vuelve a intentarlo.

---

## Sincronización con Google Sheets

La hoja de Drive se mantiene como espejo de la base de datos local. SQLite es
siempre la fuente de respuesta —por eso la app va instantánea y funciona sin
red— y Sheets es la copia legible y editable a mano.

### Cómo funciona

- **Importar (`pull`).** Se lee la hoja entera y se fusiona en SQLite. Las
  filas con `id` conocido **mandan sobre la copia local**, para que una
  edición hecha a mano en Drive se respete. Las filas sin `id` se emparejan
  por (fecha, tipo) y, si no existen, se insertan.
- **Exportar (`push`).** Se reescribe la hoja completa con el estado local.
  Con unos cientos de filas esto es más simple y fiable que llevar un diario
  de cambios fila a fila, y de paso asigna `id` a lo que se añadió a mano.
- **Cuándo.** Al arrancar, cada `SYNC_INTERVAL_MINUTES`, tras cada escritura
  (sólo `push`, en segundo plano y agrupando ráfagas) y cuando pulsas
  **Forzar sincronización**.

La hoja usa estas columnas, en este orden:

```
id | fecha | tipo | pretexto | motivacion | calidad | tiempo | observaciones
```

Al importar se aceptan variantes de cabecera habituales —`Día`, `Categoría`,
`Motivo`, `Iniciativa`, `Nota`, `Duración`, `Comentarios`…— sin distinguir
mayúsculas ni acentos, y las fechas valen en ISO, `dd/mm/aaaa`, `dd-mm-aa` o
como número de serie de Sheets.

### Dar de alta la Cuenta de Servicio

1. En [Google Cloud Console](https://console.cloud.google.com/), crea un
   proyecto y activa **Google Sheets API** y **Google Drive API**.
2. **IAM y administración → Cuentas de servicio → Crear**. No necesita
   ningún rol de IAM.
3. En la cuenta creada: **Claves → Añadir clave → Crear nueva → JSON**.
   Guarda el fichero como `credentials.json` en la raíz del proyecto.
4. Abre tu hoja en Drive y **compártela como Editor** con el correo de la
   cuenta de servicio (`...@....iam.gserviceaccount.com`).
5. Descomenta el montaje de `credentials.json` en `docker-compose.yml`, pon
   `SYNC_ENABLED=true` y levanta el stack.

`credentials.json` está en `.gitignore`: no acaba nunca en el repositorio.

---

## Las dos vistas

### `/` — Dashboard de escritorio

- **Calendario** mensual y anual con intensidad de color proporcional a la
  calidad/tiempo del encuentro. Un clic en un día abre su registro o crea uno
  nuevo con la fecha ya puesta.
- **Panel de KPIs**: días desde el último Kiki, totales, medias de calidad y
  tiempo, mayor sequía registrada y métricas de ciclo (día del ciclo, duración
  media, próxima prevista).
- **Filtros** —año, tipo, motivación, pretexto, calidad ≥, tiempo ≥ y búsqueda
  libre— en una sola fila que afecta a todo lo que hay debajo.
- **Seis gráficos**, cada uno con su gemela en tabla a un clic.
- **Tabla de registros** con ordenación por columna, paginación y edición o
  borrado en línea.

En pantallas de menos de 720 px el dashboard redirige a la PWA. Para forzarlo
igualmente: `/?desktop=1`.

### `/m` — PWA móvil

- Formulario de entrada rápida: fecha (Hoy/Ayer por defecto), tipo, calidad y
  tiempo con botones grandes de 0 a 4, motivación, pretexto y observaciones.
- Instalable en la pantalla de inicio de iOS y Android (`manifest.webmanifest`
  + iconos *maskable*).
- **Funciona sin conexión**: el Service Worker cachea el esqueleto de la app y
  las últimas respuestas de la API. Si guardas un registro sin red, se encola
  en el dispositivo y se envía solo al recuperar la conexión.
- Pestaña de historial con los últimos 50 registros y borrado rápido.

---

## API REST

Documentación interactiva en **`/docs`** (OpenAPI/Swagger, generada por
FastAPI).

| Método | Ruta | Qué hace |
| :--- | :--- | :--- |
| `GET` | `/api/events` | Lista con filtros, orden y paginación. |
| `POST` | `/api/events` | Crea un registro. |
| `GET` | `/api/events/{id}` | Devuelve un registro. |
| `PUT` | `/api/events/{id}` | Actualiza un registro. |
| `DELETE` | `/api/events/{id}` | Elimina un registro. |
| `GET` | `/api/options` | Tipos, motivaciones, pretextos usados y años con datos. |
| `GET` | `/api/stats/summary` | KPIs, distribuciones, sequías y ciclo. |
| `GET` | `/api/stats/monthly` | Serie de los doce meses de un año. |
| `GET` | `/api/stats/yearly` | Serie histórica por año. |
| `GET` | `/api/stats/breakdown` | Reparto por motivación y por pretexto. |
| `GET` | `/api/stats/calendar` | Eventos agrupados por día. |
| `GET` | `/api/sync` | Estado de la sincronización. |
| `POST` | `/api/sync?direction=both\|pull\|push` | Fuerza una sincronización. |
| `GET` | `/api/health` | Estado del servicio (lo usa el healthcheck). |

Filtros aceptados por los endpoints de listado y estadísticas: `year`,
`desde`, `hasta`, `tipo`, `motivacion`, `pretexto`, `min_calidad`,
`min_tiempo` y `q`. Los de lista añaden `sort`, `order`, `limit` y `offset`.

```bash
# Los Kikis de 2026 con calidad 4, del más reciente al más antiguo
curl 'localhost:8080/api/events?year=2026&tipo=Kiki&min_calidad=4&order=desc'

# Crear un registro
curl -X POST localhost:8080/api/events \
  -H 'Content-Type: application/json' \
  -d '{"fecha":"2026-03-10","tipo":"Kiki","calidad":4,"tiempo":3,
       "motivacion":"Ambos","pretexto":"Aniversario"}'
```

---

## Modelo de datos

| Campo | Tipo | Valores | Descripción |
| :--- | :--- | :--- | :--- |
| `id` | entero | autoincremental | Identificador único. |
| `fecha` | texto | `YYYY-MM-DD` | Día del registro. |
| `tipo` | texto | `Kiki`, `No Kiki`, `Marea` | Categoría principal. |
| `pretexto` | texto | opcional | Motivo o detonante. |
| `motivacion` | texto | `Propia`, `Ajena`, `Ambos` | De quién surgió la iniciativa. |
| `calidad` | entero | `0`–`4` | Valoración del encuentro. |
| `tiempo` | entero | `0`–`4` | Valoración de la duración. |
| `observaciones` | texto | opcional | Notas libres. |

Dos reglas se aplican en el servidor, así que valen igual desde la API que
desde cualquiera de las dos vistas:

- `calidad` y `tiempo` **se fuerzan a 0** en los registros que no son `Kiki`.
- Los textos se recortan, los vacíos pasan a nulos y `motivacion` se normaliza
  (`ambos` → `Ambos`).

Un mismo día admite varios registros: un `Kiki` y una `Marea` conviven sin
problema, y el calendario lo refleja con un punto indicador.

---

## Desarrollo

```bash
# Backend
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
DATA_DIR=./data .venv/bin/python -m pytest tests/ -q

# Frontend: Tailwind compilado + librerías vendorizadas
npm install
npm run build          # build:css + vendor
npm run watch:css      # recompila al vuelo mientras editas plantillas
node tools/icons.mjs   # regenera los PNG de los iconos desde los SVG
```

Los assets compilados (`static/css/app.css`, `static/vendor/`) **están
versionados a propósito**: así la imagen Docker no necesita Node y se
construye sólo con Python. Si tocas `frontend/app.css`, las plantillas o el
JS, vuelve a lanzar `npm run build` y commitea el resultado.

Alpine.js y Chart.js se sirven desde el propio contenedor, no desde un CDN: la
PWA tiene que arrancar sin red y el despliegue no debe depender de terceros.

---

## Estructura del proyecto

```
app/
├── main.py              FastAPI: rutas de vistas, estáticos y arranque
├── config.py            Configuración por variables de entorno
├── db.py                Conexión SQLite, esquema y metadatos
├── crud.py              Consultas y escrituras sobre `events`
├── stats.py             KPIs, series, sequías y métricas de ciclo
├── schemas.py           Modelos Pydantic y vocabulario del dominio
├── routers/             events · statistics · sync
└── services/
    ├── sheets.py        Pasarela gspread y normalización de filas
    └── sync.py          Orquestación pull/push y tareas en segundo plano

frontend/app.css         Fuente de Tailwind (tokens y componentes)
templates/               dashboard.html · mobile.html
static/
├── css/app.css          Tailwind compilado (generado)
├── js/                  core · charts · dashboard · mobile
├── vendor/              Alpine.js y Chart.js (generado)
├── icons/               SVG fuente y PNG generados
├── manifest.webmanifest
└── sw.js                Service Worker
tools/                   seed.py · vendor.mjs · icons.mjs
tests/                   Suite de pytest
```

---

## Decisiones de diseño

**Los colores no son decorativos.** La paleta de series está validada para
daltonismo y contraste sobre el fondo oscuro de la app: verde `#199e70` para
Kiki, naranja `#d95926` para No Kiki y violeta `#9085e9` para Marea. Comparando
todos los pares, el peor caso simulando deuteranopía es ΔE 9.4 y el peor caso
con visión normal es ΔE 20.9; los tres superan 3:1 de contraste. En el
calendario, la intensidad del verde es una rampa de un solo tono (0→4), nunca
un arcoíris.

**El color nunca es el único canal.** Cada gráfico tiene leyenda y una gemela
en tabla a un clic, los tipos llevan etiqueta de texto junto al punto de
color, y la tinta de las celdas coloreadas se calcula contra el relleno real
para que siempre supere el contraste.

**SQLite primero, Sheets después.** Toda lectura se responde en local. La
sincronización va en segundo plano y, si falla, la app sigue funcionando y lo
dice en la cabecera en lugar de bloquear la escritura.

**Sin build de JavaScript.** Alpine.js para la reactividad y Chart.js para los
gráficos, cargados como scripts. No hay bundler, ni paso de transpilación, ni
`node_modules` en la imagen final.
