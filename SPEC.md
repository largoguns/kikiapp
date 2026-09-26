# Especificación Técnica para Desarrollo de Aplicación Web "Kiki App"

## 1. Visión General del Proyecto
**Kiki App** es una aplicación web ligera, dockerizable e intuitiva para el registro y análisis de encuentros/desencuentros de pareja, seguimiento del período menstrual y métricas asociadas. La aplicación debe contar con un **Dashboard completo de Escritorio** y una **PWA móvil ultraligera** orientada a la rápida introducción de datos.

---

## 2. Arquitectura de Datos y Estrategia de Sincronización

### 2.1 Origen de Datos (Google Sheets / CSV Persistence)
Para mantener la hoja de cálculo de Google Drive ("Kiki") como origen de datos o espejo:
* **Estrategia Recomendada:**
  * **Backend Storage Primary:** Base de datos SQLite local o archivo JSON/CSV interno en el contenedor Docker para respuesta instantánea, offline-first y nula latencia.
  * **Sincronización Bidireccional / Sync con Google Sheets API:**
    * Implementar un módulo de integración usando `gspread` (Python) o la SDK oficial de Google Sheets con una **Cuenta de Servicio (Service Account)**.
    * **Lectura/Importación:** Sincronización inicial al arrancar y tarea programada (cron/background task cada X horas) o botón manual de "Forzar Sincronización".
    * **Escritura/Exportación:** Al añadir o modificar un registro desde la PWA/Dashboard, el backend escribe en la BBDD local y realiza un append/update asíncrono en la Google Sheet.

### 2.2 Esquema de Datos (`Kikis` / Registros)
Basado en la estructura real del archivo actual:

| Campo | Tipo | Valores / Rango | Descripción |
| :--- | :--- | :--- | :--- |
| `id` | Integer / UUID | Autoincremental | Identificador único del evento. |
| `fecha` | Date (`YYYY-MM-DD`) | Fecha válida | Día del registro. |
| `tipo` | Enum / String | `Kiki` (Encuentro), `No Kiki` (Desencuentro), `Marea` (Menstruación) | Categoria principal. |
| `pretexto` | String / Opcional | `Desatranque`, `Cumpleaños`, `Calentura`, `Necesidad`, `Aniversario`, `N/A`, etc. | Motivo/detonante. |
| `motivacion` | Enum / String | `Propia`, `Ajena`, `Ambos` | De quién surgió la iniciativa. |
| `calidad` | Integer | `0` (en No Kiki) a `4` (Máxima) | Valoración de la calidad del encuentro. |
| `tiempo` | Integer | `0` (en No Kiki) a `4` (Máxima) | Valoración de la duración/tiempo. |
| `observaciones` | Text / Opcional | Texto libre | Comentarios o notas adicionales. |

---

## 3. Stack Tecnológico Sugerido (Ligero y Eficiente)

* **Backend:** Python (FastAPI / Flask) o Node.js (Express / Fastify).
  * *Recomendación:* **FastAPI (Python)** por su ligereza, auto-documentación OpenAPI (Swagger) y facilidad para integrarse con `pandas` / `gspread` para la sincronización con Google Sheets.
* **Frontend:**
  * **Desktop Dashboard:** HTML5 + Tailwind CSS + Vanilla JS / Alpine.js + Chart.js / FullCalendar.js (o componentes ligeros Svelte / Vue sin sobrecarga).
  * **Mobile PWA:** HTML/Web Manifest + Service Worker + Tailwind CSS + Vanilla JS (diseño app-like nativo, carga instantánea).
* **Base de Datos Local:** SQLite (fichero `.db` persistido en volumen Docker).

---

## 4. Requisitos de las Vistas

### 4.1 Vista Escritorio (Dashboard Completo)
1. **Calendario Interactivo con Indicadores de Color:**
   * **Verde / Azul / Tonalidad cálida:** Días con "Kiki" (encuentro positivo). Intensidad del color proporcional a la calidad/tiempo.
   * **Rojo / Naranja:** Días con "No Kiki" (desencuentro).
   * **Rosa / Púrpura:** Días de "Marea" (período menstrual).
   * **Negro / Gris:** Días sin actividad o marcados explícitamente.
2. **Panel de Métricas y KPIs:**
   * **Contador de Días sin Eventos Positivos:** Muestra dinámica de días transcurridos desde el último "Kiki" (`Días desde el último Kiki`).
   * **Totales Mensuales y Anuales:** Número de Kikis vs. No Kikis por mes y año.
   * **Promedios de Calidad y Tiempo:** Medias filtrables.
3. **Filtros Avanzados:**
   * Filtrado por **Año** (2024, 2025, 2026, Histórico).
   * Filtrado por **Valoración** (Calidad >= X, Tiempo >= Y).
   * Filtrado por **Motivación** (`Propia`, `Ajena`, `Ambos`) y **Pretexto**.
4. **Tabla de Registros:**
   * Listado completo con ordenación, búsqueda y opción de editar/eliminar entradas.

### 4.2 Vista Móvil (PWA - Progressive Web App)
1. **Diseño Mobile-First:** Interfaz táctil, botones grandes, carga ultrarrápida.
2. **Formulario Simplificado de Entrada Rápida:**
   * Selector de Fecha (por defecto HOY).
   * Selector de Tipo (Kiki / No Kiki / Marea).
   * Selector por estrellas/puntos para **Calidad** (0 a 4) y **Tiempo** (0 a 4).
   * Desplegable de Motivación (`Propia`, `Ajena`, `Ambos`) y Pretexto.
   * Campo de Texto para Observaciones/Comentarios.
3. **Soporte PWA:**
   * Manifest web (`manifest.json`) e icono instalable en pantalla de inicio de iOS/Android.
   * Service Worker para funcionamiento fluído.

---

## 5. Requisitos de Despliegue (Docker & Portainer)

### 5.1 `Dockerfile`
* Contenedor base multi-stage o Python Alpine / Slim para mantener la imagen < 150MB.

### 5.2 `docker-compose.yml`
```yaml
version: '3.8'

services:
  kiki-app:
    build: .
    container_name: kiki_app
    restart: unless-stopped
    ports:
      - "8080:8080"
    environment:
      - PORT=8080
      - GOOGLE_SHEETS_CREDENTIALS_FILE=/app/credentials.json
      - GOOGLE_SHEET_NAME=Kiki
      - TZ=Europe/Madrid
    volumes:
      - kiki_data:/app/data
      - ./credentials.json:/app/credentials.json:ro

volumes:
  kiki_data:
```

---

## 6. Instrucciones Directas para el Agente de IA de Implementación

> **Instrucción para el Agente:**
> Construye la aplicación web **Kiki App** siguiendo la especificación previa.
> 1. Crea la estructura completa del proyecto con FastAPI en backend y TailwindCSS + Vanilla JS / Alpine.js en frontend.
> 2. Implementa los endpoints REST API para CRUD de eventos, estadísticas y sincronización con Google Sheets vía `gspread`.
> 3. Diseña el Dashboard de Escritorio con vistas de calendario mensual/anual y panel de KPIs.
> 4. Diseña la vista PWA móvil optimizada con manifest y formulario rápido.
> 5. Proporciona el `docker-compose.yml` y `Dockerfile` listos para desplegar en Portainer.
