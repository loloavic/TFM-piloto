# Seguridad y privacidad: fase 1

## Alcance y compatibilidad

La clasificación, enriquecimiento, recuperación RAG, embeddings, prompt funcional y generación del LLM mantienen su implementación. Se añade una frontera de minimización a la entrada del servicio y a la salida del nodo generador, antes de que LangGraph guarde su resultado.

La consulta inicial `POST /api/v1/consultas` sigue siendo pública y conserva el esquema JSON de respuesta. La cabecera de respuesta **`X-Session-Token`** contiene una credencial aleatoria de 256 bits. Para continuar hay que enviar esa cabecera y el `session_id` del JSON. El UUID es un identificador, no una autorización. El servidor guarda únicamente el SHA-256 de la credencial y compara los hashes en tiempo constante. La credencial autoriza únicamente su sesión; no es identidad civil ni autenticación de una cuenta.

Cambios de contrato intencionados:

- Continuar una sesión existente sin credencial correcta devuelve **403**, antes de ejecutar el grafo. Un token de otra sesión tampoco sirve. Una sesión desconocida presentada con una credencial antigua no se recrea. Se inicia una conversación nueva omitiendo ambos campos, o presentando un UUID nuevo sin token.
- Los identificadores elegidos por el cliente deben ser UUID con guiones; clientes con identificadores arbitrarios deben dejar que el servidor genere el UUID.
- El campo `pregunta` de la respuesta y las respuestas generadas pasan por redacción parcial. Por ello pueden contener marcadores de redacción.
- `GET /api/v1/evaluacion/resumen` y `/api/v1/evaluacion/consultas` requieren `Authorization: Bearer <INTERNAL_API_TOKEN>`. Sin secreto configurado se deshabilitan con **503**; sin credencial o con una incorrecta, **401**. No poner el secreto administrativo en Gradio, JavaScript público ni n8n público.
- Los registros nuevos conservan fecha, intención de una lista cerrada y estado reducido de verificación. Las columnas históricas `pregunta`, `respuesta` y `fuentes` se conservan en el esquema, pero están vacías o contienen `[]`. El resumen por fuentes deja de disponer de ese detalle. `limite` se acota a 1–100.
- `DELETE /api/v1/sesiones/{session_id}` requiere la misma cabecera de sesión y devuelve **204** tras eliminar sus checkpoints, escrituras, blobs y autorización. Sin credencial válida devuelve **403** sin revelar si existe.

Las respuestas autorizadas de consulta y evaluación tienen `Cache-Control: no-store`. El cliente debe mantener el token fuera de URLs, registros y almacenamiento compartido. No imprimir el diccionario completo devuelto por `RAGService`, que incluye la credencial para clientes internos; seleccionar los campos necesarios.

## Minimización, no anonimización completa

`app/core/privacy.py` redacta correos electrónicos, secuencias numéricas contiguas de al menos ocho dígitos, ciertos identificadores alfanuméricos etiquetados como DNI/pasaporte/NIE/NIF y teléfonos internacionales con `+`. Se conserva el texto restante para no sustituir el clasificador ni el prompt.

Esto es **redacción parcial**, no anonimización. No detecta de forma exhaustiva nombres, domicilios, identificadores escritos con palabras, formatos fragmentados o datos inferibles. También puede producir falsos positivos, incluso ocultar un correo oficial en la salida. La advertencia de no introducir datos personales sigue siendo necesaria. El proveedor recibe el texto reducido y su historial reducido; todavía podría recibir datos que no detecten estos filtros. No usar esta fase como justificación de cumplimiento normativo o para admitir datos sensibles reales sin evaluación adicional.

El texto original se procesa transitoriamente en la petición HTTP, pero no se pasa como entrada al grafo. El nodo generador reduce su salida antes de crear checkpoints; los turnos posteriores usan ese historial reducido. Los registros de aplicación nuevos no almacenan texto libre, identificadores de sesión ni tokens. Esto no controla los registros de un proxy, APM, servidor externo o proveedor LLM: deben configurarse por separado.

## Política real de retención

Se usa la capacidad pública `InMemorySaver.delete_thread(thread_id)` de la versión instalada de LangGraph. Se comprobó que borra sus tres almacenes: `storage`, `writes` y `blobs`. No se manipulan sus estructuras privadas en producción.

- Duración **absoluta** por sesión: `SESSION_TTL_SECONDS`, 1800 segundos por defecto. Consultar la sesión no renueva su vencimiento.
- Barrido periódico: `SESSION_CLEANUP_INTERVAL_SECONDS`, 30 segundos por defecto, incluso sin peticiones nuevas. También se limpia al acceder o borrar sesiones y al terminar una operación.
- Durante una sesión se conservan los checkpoints de sus ejecuciones. La lista funcional de seis turnos no equivale a seis checkpoints. Al vencer se borra **todo** el hilo; no se promete eliminación de cada turno tras salir de esa lista.
- Autorización, ejecución del grafo y borrado están serializados mediante un cerrojo. Así el barrido no borra un hilo mientras una ejecución pudiera volver a escribirlo. Una llamada en curso no se cancela al vencer: el borrado ocurre al finalizar y limpiar. En reposo la demora habitual máxima es TTL más un intervalo de barrido, sujeta al planificador. No se promete una cota estricta durante llamadas externas bloqueadas.
- Un fallo después de entrar al grafo elimina también checkpoints parciales y revoca la sesión; el cliente debe iniciar una nueva. Un fallo de autorización no borra una sesión válida.
- Cerrar el servicio elimina todos sus hilos. FastAPI arranca/detiene el barrido en su lifespan. El servicio también lo inicia de forma diferida en su primera consulta para cubrir uso directo desde Python. Llamar a `service.sessions.close()` al finalizar ese uso.
- `SESSION_MAX_COUNT`, 256 por defecto, limita sesiones simultáneas. Al alcanzar el máximo se responde 503; no se expulsa arbitrariamente una sesión válida.

El borrado elimina referencias de los almacenes de Python; no constituye borrado forense de RAM, swap, volcados o snapshots. La política no controla retención en OpenAI ni copias de seguridad.

## Gradio

La credencial se conserva junto al UUID en un `gr.State` de servidor y no se incluye en la conversación ni en los metadatos mostrados. Nueva conversación elimina explícitamente el hilo previo. El estado tiene TTL y callback de eliminación; el servicio conserva además su barrido propio. Los errores públicos ya no muestran el texto de excepciones internas.

Las sesiones de API y Gradio pertenecen a servicios distintos, como antes. No hay continuidad de sesión entre canales. El historial que ya recibió el navegador no puede revocarse con el borrado del servidor; el usuario debe cerrar o limpiar su conversación. Proteger también la infraestructura de Gradio, sus sesiones y acceso a red.

## Variables y despliegue

| Variable | Valor por defecto | Requisito |
|---|---|---|
| `INTERNAL_API_TOKEN` | Ausente | Secreto administrativo fuerte y exclusivo, generado con un CSPRNG; ausencia o cadena vacía deshabilita evaluación. |
| `SESSION_TTL_SECONDS` | `1800` | Entero entre 1 y 86400. |
| `SESSION_CLEANUP_INTERVAL_SECONDS` | `30` | Entero entre 1 y 300. |
| `SESSION_MAX_COUNT` | `256` | Entero entre 1 y 10000. |

No se añaden dependencias. Inyectar el secreto con el gestor de secretos del despliegue; no incluir valores reales en Git ni en chat. Rotarlo requiere reiniciar el proceso y actualizar los clientes administrativos.

Este backend es de **un solo proceso por canal**: ejecutar FastAPI con `--workers 1` y una sola réplica. No usar balanceo entre instancias con almacenes independientes. Reiniciar elimina conversaciones y credenciales en memoria; un token anterior se rechaza. Antes de escalar hay que sustituir conjuntamente sesiones, coordinación y checkpointer por un almacenamiento compartido con las mismas garantías de autorización, TTL y eliminación. El cerrojo global reduce la concurrencia y una llamada lenta puede retrasar otras; no se afirma haber resuelto disponibilidad bajo abuso. TLS, límites de petición y cuotas en el proxy siguen siendo necesarios.

### Datos anteriores y puesta en marcha

1. Detener las instancias antiguas de FastAPI/Gradio antes de desplegar. Sus checkpoints no son migrados ni autorizados por el nuevo servicio.
2. Inventariar `data/logs/consultas_log.csv`, CSV de evaluación, notebooks con salidas y copias/snapshots existentes. Pueden contener texto personal. Esta implementación **no los destruye automáticamente**: deben retirarse del servicio y eliminarse o custodiarse con una política autorizada, incluida la gestión de copias. No copiarlos al nuevo fichero de métricas.
3. El nuevo servicio escribe y lee únicamente `data/logs/consultas_metricas.csv`. El lector además elimina columnas de texto si se le proporciona un fichero antiguo. El archivo histórico no vuelve a exponerse mediante estos endpoints.
4. Configurar secreto, TTL y límites, y reiniciar con una sola réplica. Verificar sin credencial el rechazo de evaluación, y después con un cliente autorizado. Evitar captura de cabeceras y cuerpos en proxies/APM.
5. Adaptar clientes para capturar/reutilizar `X-Session-Token` y para borrar conversaciones al terminar. Un cliente n8n, si se implementa, debe almacenar cada par de credenciales de forma aislada; no reutilizar una sesión global.

## Pruebas reproducibles sin OpenAI

```bash
GRADIO_ANALYTICS_ENABLED=False PYTHONDONTWRITEBYTECODE=1 \
  .venv/bin/python -B -m pytest -q -p no:cacheprovider
```

La selección predeterminada excluye seis pruebas marcadas `integration`, que siguen requiriendo OpenAI e índice FAISS. Se pueden seleccionar explícitamente con `pytest -m integration` en un entorno autorizado; no se han ejecutado durante esta fase.

Las pruebas unitarias usan el grafo y checkpointer reales, proveedor/recuperación simulados cuando procede, datos ficticios y ficheros temporales. Cubren autorización administrativa, credenciales de sesión, accesos cruzados, borrado selectivo, caducidad absoluta, barrido en reposo, artefactos parciales, cierre, minimización del prompt y checkpoints, métricas sin texto y estado privado de Gradio. No prueban calidad factual del LLM ni detección exhaustiva de datos personales.
