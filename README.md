# 🚀 Automatización Lead → Tarea (FastAPI + ClickUp)

Este proyecto implementa el reto técnico:  

> Construir una automatización que, a partir de un formulario web con datos de un lead, cree una tarea en un Task Manager vía API, almacene los datos localmente y (bono) genere subtareas.

---

## ✨ Características

- **Google Forms → Apps Script → FastAPI**  
  Los datos del lead viajan desde Google Forms (mediante Apps Script) hasta el backend.
- **Integración con Task Manager (ClickUp)**  
  Se crea una tarea en una lista configurada de ClickUp usando su API pública.  
  - **Título:** `Nuevo lead: {nombre} ({correo})`  
  - **Descripción:** incluye todos los campos y el payload JSON.  
  - **Etiquetas:** se mapean desde `intereses_servicios`.  
- **Persistencia local (SQLite)**  
  Todos los leads y metadatos de tareas se almacenan en `data/leads.db`.
- **Idempotencia**  
  Duplicados (mismo correo + fecha + nombre) devuelven el registro existente (`200 OK`).
- **Bono**  
  Se crean automáticamente subtareas como:  
  - Contactar lead (24h)  
  - Enviar información  
  - Proponer 3 horarios  
- **Logging estructurado**  
  Logs en JSON hacia consola y archivo `logs/app.log` mostrando el flujo completo:  
  formulario → validación → creación de tarea → almacenamiento → subtareas.

---

## 🛠️ Stack Tecnológico

- **Backend:** Python 3.9, FastAPI  
- **Base de datos:** SQLite + SQLAlchemy ORM  
- **Task Manager:** ClickUp REST API (plan gratuito, token personal)  
- **Webhook:** Google Forms + Apps Script  
- **Logging:** structlog (JSON logs)  
- **Túnel local (demo):** Cloudflared / ngrok (opcional)  

---

## 📂 Estructura del Proyecto

app/
├── api/routers/webhook.py # Ruta FastAPI para el webhook
├── services/lead_service.py # Lógica principal de negocio
├── integrations/clickup_client.py
├── db/models.py # Modelos SQLAlchemy
├── db/migrations.py # Migraciones ligeras (idempotentes)
├── logging_config.py # Configuración de logging
└── main.py # Punto de entrada FastAPI
data/
└── leads.db # Base local SQLite
logs/
└── app.log # Logs estructurados
.env.example # Variables de entorno
README.md # Este documento


---

## ⚙️ Instalación y Ejecución

1. **Clonar el repositorio**  
   ```bash
   git clone https://github.com/ivancalderon/formulario-api-tarea-clickup.git
   cd formulario-api-tarea-clickup


Crear y activar entorno virtual

python3.9 -m venv venv
source venv/bin/activate


Instalar dependencias

pip install -r requirements.txt


Configurar variables de entorno
Copiar .env.example a .env y completar:

CLICKUP_TOKEN=tu_token
CLICKUP_LIST_ID=tu_lista
FORM_SHARED_SECRET=un_secreto_seguro


Ejecutar el servidor

uvicorn app.main:app --reload

Activar un tunel para el Formulario
npx localtunnel --port 8000

Copiar la url producto del comando anterior (url_A)

Ir a la spreadsheet del formulario -> Configuración del Proyecto -> Propiedades de la secuencia del comando -> crear propiedad -> ENDPOINT -> Pegar url_A/api/form/webhook

crear propiedad -> FORM_SHARED_SECRET -> Pegar FORM_SHARED_SECRET desde .env

Probar con curl

curl -X POST http://localhost:8000/api/form/webhook \
  -H "Content-Type: application/json" \
  -H "X-Form-Secret: $FORM_SHARED_SECRET" \
  -d '{"nombre":"Ana Pérez","correo":"ana@example.com","telefono":"+57 3001234567","intereses_servicios":["diseño","riego"],"mensaje":"Proyecto"}'

🗂️ Esquema de Datos (SQLite)

Tabla leads:

Campo	Tipo	Descripción
id (PK)	INTEGER	Autoincremental
nombre	TEXT	Nombre del lead
correo	TEXT	Correo electrónico
telefono	TEXT	Teléfono (opcional)
intereses_servicios	TEXT	Lista en JSON
mensaje	TEXT	Mensaje libre (opcional)
external_task_id	TEXT	ID de tarea en ClickUp
external_task_url	TEXT	URL de la tarea
external_subtask_ids	TEXT	IDs de subtareas (JSON)
status_api	INTEGER	Código de estado HTTP (200, 201, etc.)
created_at	TEXT	Marca temporal ISO 8601
📊 Diagrama de Flujo
Google Forms → Apps Script → FastAPI /api/form/webhook
        → Validación & normalización
        → lead_service.create_or_get_lead
            → SQLite: guardar lead
            → ClickUp API: crear tarea
                 → (Bono) crear subtareas
        → Respuesta 201 (nuevo) o 200 (duplicado)

🧪 Pruebas

Caso básico: enviar payload → recibir 201 con task_id y task_url.

Duplicado: mismo correo + fecha → 200 con registro existente.

Validación: correo inválido → 400.

Resiliencia: error 5xx en ClickUp → reintento + log.

📜 Ejemplo de Log
{"ts":"2025-09-01T15:05:12.234Z","level":"info","event":"webhook_received","has_secret":true}
{"ts":"2025-09-01T15:05:12.241Z","level":"info","event":"lead_created","lead_id":42}
{"ts":"2025-09-01T15:05:12.815Z","level":"info","event":"tm_task_created","parent_id":"CU123456","url":"https://app.clickup.com/t/CU123456"}
{"ts":"2025-09-01T15:05:13.245Z","level":"info","event":"tm_persisted_clickup_fields","lead_id":42,"status":201,"subtask_count":3}

✅ Checklist de Entrega

 Código fuente (FastAPI + SQLite + ClickUp)

 .env.example con variables necesarias

 README.md con instalación y uso

 Esquema de datos (tabla)

 Diagrama de flujo (ASCII/Markdown)

 Log de ejemplo de flujo completo

 Export de la DB local (data/leads.db)