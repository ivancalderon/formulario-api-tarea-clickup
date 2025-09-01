+-------------------+          +--------------------------+
|   Google Forms    |          |  Google Apps Script      |
| (usuario envía)   |  ----->  |  onSubmit / doPost()     |
+---------+---------+          +-----------+--------------+
          |                                |
          | JSON con datos del lead        |  POST https://<tu-host>/api/form/webhook
          +--------------------------------v--------------------------------+
                                                                           |
                                                                +----------v----------+
                                                                |   FastAPI Webhook   |
                                                                |   /api/form/webhook |
                                                                +-----+---------+-----+
                                                                      |         |
                                                          Valida y normaliza     |
                                                      (correo, intereses, token) |
                                                                      |         |
                                                                      |         v
                                                                      |   400 Error de validación
                                                                      |
                                                                      v
                                                       +--------------+---------------+
                                                       | lead_service.create_or_get_  |
                                                       | lead(data)                   |
                                                       | - dedupe por email+fecha     |
                                                       | - guarda en SQLite           |
                                                       +------+-----------------------+
                                                              |
                                        ¿Lead nuevo? ---------+--- No --> devolver existente (200 OK)
                                                              |
                                                              v
                                      +-----------------------+----------------------+
                                      |  Adaptador ClickUp                          |
                                      |  - crea tarea (título, descripción, tags)   |
                                      |  - crea subtareas (bono)                    |
                                      |  - devuelve task_id y task_url              |
                                      +-------------------+--------------------------+
                                                          |
                                                          v
                                  +-----------------------+-------------------------+
                                  | Actualizar fila en SQLite:                      |
                                  | external_task_id, external_task_url,            |
                                  | external_subtask_ids, status_api                |
                                  +-----------------------+-------------------------+
                                                          |
                          +-------------------------------+-------------------------------+
                          |                                                               |
                          v                                                               v
              201 Created (lead nuevo)                                     200 OK (lead duplicado)
        Body: { ok, task_id, task_url, ... }                         Body: { ok, storage_id, ... }

Logs: incluyen respuestas de API, errores, reintentos (5xx) y timestamps.

Errores:
- Validación → 400 con mensaje claro
- Error externo (429/5xx) → reintento x1; si falla → 502/504 con retryable: true
