# Kiki App

Aplicación web ligera para registrar y analizar **encuentros (Kiki)**,
**desencuentros (No Kiki)** y el **período menstrual (Marea)**, con un
dashboard completo de escritorio y una PWA móvil pensada para apuntar un
registro en tres toques.

Todo vive en un único contenedor: FastAPI sirve la API y las dos vistas, y
los datos se guardan en SQLite dentro de un volumen. **La app es la fuente de
verdad**; el histórico que vivía en la hoja de cálculo se trae una sola vez
con el importador.

No habla con ningún servicio externo: no hay credenciales, ni claves de API,
ni secretos que gestionar en Portainer.

---

## Índice

- [Puesta en marcha](#puesta-en-marcha)
- [Configuración](#configuración)
- [Importar el histórico](#importar-el-histórico)
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

La imagen **se construye en el propio servidor** a partir del código del
repositorio: no hay nada publicado en Docker Hub ni en ningún otro registro.
El `image: kiki-app:latest` del compose es sólo la etiqueta local que recibe
la imagen recién construida, y `pull_policy: build` obliga a reconstruirla en
lugar de intentar descargarla. Para desplegar una versión nueva basta con
hacer push al repositorio y pulsar **Update the stack** en Portainer.

### En local, sin Docker

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

DATA_DIR=./data .venv/bin/python -m uvicorn app.main:app --reload --port 8080
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

Ninguna es un secreto, así que se pueden poner directamente en el stack de
Portainer sin más cuidado.

---

## Importar el histórico

Pensado para usarse **una vez**, al estrenar la app. Se sube el fichero desde
**Importar histórico** en el dashboard, o con el endpoint `POST /api/import`.
Acepta `.xlsx` y `.csv`, y todo el proceso ocurre en local: no hace falta
compartir nada ni dar acceso a Drive.

### De dónde sale cada cosa

El libro original guarda la información repartida en dos sitios, y el
importador lee ambos:

- **La pestaña de datos** (`Kikis`) trae los encuentros con pretexto,
  motivación, valoraciones y observaciones. De las varias pestañas del libro
  se queda con la que más filas válidas produce, así que los calendarios se
  descartan solos. También se puede forzar una pestaña concreta.
- **Las pestañas de calendario** (una por año) marcan la menstruación
  pintando de rojo la celda del día. Esos días no aparecen en la tabla, así
  que se leen del color de relleno.

Se aceptan alias de cabecera habituales —`Día`, `Categoría`, `Motivo`,
`Iniciativa`, `Nota`, `Duración`, `Comentarios`— sin distinguir mayúsculas ni
acentos, y las fechas valen en ISO, `dd/mm/aaaa`, `dd-mm-aa` o como número de
serie de la hoja. Un `N/A` en el pretexto se guarda como "sin pretexto".

### Dos deducciones, y por qué son seguras

- **El tipo.** La hoja original no tiene columna de tipo: marca el
  desencuentro poniendo `calidad` y `tiempo` a 0. Nunca deja sólo una de las
  dos a cero, así que la regla `0/0 → No Kiki` sale del propio fichero, no de
  una suposición. Si algún día la hoja trae columna de tipo, esa manda.
- **La Marea.** Se clasifica por **tono**, no por el hex exacto, así que vale
  igual un rojo pleno que un rosa claro o un granate. Los colores que no son
  rojos no se descartan en silencio: el informe los lista con su recuento,
  para que se vea qué se ha dejado fuera.

### Modos

- **Combinar** (por defecto): inserta lo que falta y deja intacto lo que ya
  existe, emparejando por (fecha, tipo). Repetir la importación no duplica
  nada.
- **Reemplazar**: vacía la tabla antes de insertar. Pide confirmación.

El botón **Analizar** hace una pasada en seco: enseña el informe completo
—cuántos registros de cada tipo, el rango de fechas, las filas descartadas—
sin escribir nada en la base de datos.

### Desde la consola

```bash
# Vista previa, sin tocar los datos
docker compose exec kiki-app python tools/import_file.py /app/data/Kiki.xlsx --simular

# Importar de verdad
docker compose exec kiki-app python tools/import_file.py /app/data/Kiki.xlsx
```

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

> **La instalación y el modo offline exigen HTTPS.** Los navegadores sólo
> consideran contexto seguro a `https://` y a `localhost`, y fuera de ahí ni
> siquiera exponen `navigator.serviceWorker`. Entrando por
> `http://192.168.x.x:8080` la app funciona con normalidad, pero Chrome
> responde «esta aplicación no se puede instalar» y no hay caché offline ni
> cola de envíos.
>
> Para resolverlo, pon un HTTPS con certificado válido delante del contenedor:
> `tailscale serve`, o un proxy inverso —Caddy, Nginx Proxy Manager, Traefik—
> con Let's Encrypt. Un certificado autofirmado no vale: Chrome tampoco
> instala la PWA en ese caso.
>
> Para una prueba rápida en un solo dispositivo, Chrome permite marcar un
> origen concreto como seguro en
> `chrome://flags/#unsafely-treat-insecure-origin-as-secure`.

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
| `GET` | `/api/import` | Cuándo fue la última importación. |
| `POST` | `/api/import` | Sube un `.xlsx` o `.csv` (multipart: `archivo`, `modo`, `simular`). |
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
├── routers/             events · statistics · importer
└── services/
    └── importer.py      Lectura de .xlsx/.csv y de los calendarios por color

frontend/app.css         Fuente de Tailwind (tokens y componentes)
templates/               dashboard.html · mobile.html
static/
├── css/app.css          Tailwind compilado (generado)
├── js/                  core · charts · dashboard · mobile
├── vendor/              Alpine.js y Chart.js (generado)
├── icons/               SVG fuente y PNG generados
├── manifest.webmanifest
└── sw.js                Service Worker
tools/                   import_file.py · seed.py · vendor.mjs · icons.mjs
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

**Una sola fuente de verdad.** La app manda; la hoja de cálculo fue el punto
de partida, no un espejo permanente. Eso elimina toda una clase de problemas
—conflictos de escritura, credenciales, cuotas de API, fallos de red— a
cambio de un importador que se usa una vez.

**Nada se descarta en silencio.** El informe de importación dice qué pestaña
se ha usado, cuántas filas se han descartado y qué colores de calendario no
se han interpretado como Marea. Si el fichero trae algo que el importador no
entiende, se ve.

**Sin build de JavaScript.** Alpine.js para la reactividad y Chart.js para los
gráficos, cargados como scripts. No hay bundler, ni paso de transpilación, ni
`node_modules` en la imagen final.
