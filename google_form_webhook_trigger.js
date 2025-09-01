/**
 * Google Forms → Apps Script → FastAPI Webhook
 *
 * ⚙️ Configuración del Proyecto (Click en la rueda dentada) → Propiedades de Secuencia de Comandos → Crear:
 *   ENDPOINT = https://<url-publica-de-prueba>/api/form/webhook → Url obtenida desde el servidor de prueba con el comando npx localtunnel --port 8000 
 *   FORM_SHARED_SECRET = <secreto-de-verificacion-de-acceso>
 *
 * ⏰ Activadores:
 *   - Activadores (Click en el reloj) → Añadir Activador
 *     Función: onSubmit
 *     Selecciona una fuente del evento: Desde hoja de cálculo
 *     Selecciona el tipo de evento: Al enviarse el formulario
 *
 * 
 */

function onSubmit(e) {
  // e es JSON que contiene la información del lead después de completar el formulario.
  // Importar variables de configuración
  const props = PropertiesService.getScriptProperties();
  const ENDPOINT = props.getProperty('ENDPOINT');
  const SECRET = props.getProperty('FORM_SHARED_SECRET');

  if (!ENDPOINT || !SECRET) {
    Logger.log('No existe configuración. Definir propiedades ENDPOINT y FORM_SHARED_SECRET.');
    return;
  }

  // e.namedValues looks like: { "Nombre": ["Ana"], "Correo electrónico": ["ana@..."], ... }
  //const named = e && e.namedValues ? e.namedValues : {};
  const named = e?.namedValues ?? {};

  // Normalize: lowercase, strip accents, replace non-word chars with underscore
  const norm = s => s
    ? s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^\w]+/g, '_')
    : '';

  // Build normalized map of "question title" -> answers (array)
  /*
  const m = {};
  Object.keys(named).forEach(k => { m[norm(k)] = named[k]; });
*/
  const m = Object.fromEntries(
  Object.entries(named).map(([k, v]) => [norm(k), v])
  );

  // Helpers
  const first = (arr) => Array.isArray(arr) && arr.length ? String(arr[0]).trim() : '';
  const optional = (arr) => {
    const v = first(arr);
    return v ? v : null;
  };
  // Checkboxes: may come as ["a, b"] or ["a","b"]
  const parseMulti = (arr) => {
    if (!Array.isArray(arr) || !arr.length) return [];
    if (arr.length > 1) return arr.map(s => String(s).trim()).filter(Boolean);
    return String(arr[0]).split(',').map(s => s.trim()).filter(Boolean);
  };

  // Pick first present field from a list of human labels (pretty) and/or canonical
  const pickByLabels = (map, labels) => {
    for (const label of labels) {
      const key = norm(label);
      if (map[key] != null) return map[key];
    }
    return undefined;
  };

  // Define the label variants you actually use in your Form (extend as needed)
  const payload = {
    nombre: first(pickByLabels(m, ['Nombre', 'nombre'])),
    correo: first(pickByLabels(m, ['Correo', 'Correo electrónico', 'Email', 'correo', 'correo electrónico', 'email'])),
    telefono: optional(pickByLabels(m, ['Teléfono', 'telefono', 'Teléfono de contacto'])),
    intereses_servicios: parseMulti(pickByLabels(m, [
      'Servicios de Interés', 'Intereses', 'Intereses / Servicios', 'Servicios', 'intereses_servicios', 'servicios de interes'
    ])),
    mensaje: optional(pickByLabels(m, ['Mensaje', 'Comentarios', 'Detalle', 'Descripción', 'descripcion', 'mensaje'])),
  };

  // DEBUG (temporary): comment out after first good run
  //Logger.log('Incoming labels: %s', JSON.stringify(Object.keys(named)));
  //Logger.log('Normalized keys: %s', JSON.stringify(Object.keys(m)));
  //Logger.log('Payload preview: %s', JSON.stringify(payload));

  // Lightweight validation; FastAPI will do strict validation again
  if (!payload.nombre || !payload.correo) {
    Logger.log('Missing required fields. Payload=%s', JSON.stringify(payload));
    return;
  }

  const options = {
    method: 'post',
    contentType: 'application/json',
    headers: { 'X-Form-Secret': SECRET }, // secret is read from Script Properties (not hard-coded)
    payload: JSON.stringify(payload),
    muteHttpExceptions: true,
    followRedirects: true,
    validateHttpsCertificates: true,
  };

  try {
    const res = UrlFetchApp.fetch(ENDPOINT, options);
    Logger.log('Webhook status=%s body=%s', res.getResponseCode(), res.getContentText());
  } catch (err) {
    Logger.log('Webhook error: %s', err && err.message ? err.message : String(err));
  }
}


/**
 * Simulate a submission using professional labels (pretty names).
 * Run from the Apps Script editor to test end-to-end quickly.
 */
function testPostPrettyLabels() {
  const e = {
    namedValues: {
      'Nombre': ['Ana Pérez'],
      'Correo electrónico': ['ana@example.com'],
      'Teléfono': ['+57 3001234567'],
      'Servicios de interés': ['diseño, riego'],
      'Mensaje': ['Proyecto de jardín frontal'],
    }
  };
  onSubmit(e);
}

/**
 * Simulate a submission using canonical keys (for debugging).
 */
function testPostCanonical() {
  const e = {
    namedValues: {
      'nombre': ['Ana Pérez'],
      'correo': ['ana@example.com'],
      'telefono': ['+57 3001234567'],
      'intereses_servicios': ['diseño, riego'],
      'mensaje': ['Proyecto de jardín frontal'],
    }
  };
  onSubmit(e);
}

/**
 * Log whether configuration properties are present (does not print values).
 */
function showConfig() {
  const props = PropertiesService.getScriptProperties();
  const hasEndpoint = !!props.getProperty('ENDPOINT');
  const hasSecret = !!props.getProperty('FORM_SHARED_SECRET');
  Logger.log('Config present → ENDPOINT: %s, FORM_SHARED_SECRET: %s', hasEndpoint, hasSecret);
}

showConfig();
testPostPrettyLabels();

