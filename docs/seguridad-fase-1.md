# Seguridad y privacidad: fase 1 y correcciones R1–R5

## Contrato público y límites de alcance

La consulta inicial `POST /api/v1/consultas` sigue siendo pública. Su cabecera de respuesta `X-Session-Token` contiene una credencial aleatoria de 256 bits; continuar requiere esa cabecera y el `session_id` del JSON. El UUID no es autorización. Solo se guarda el hash SHA-256 de la credencial, con comparación en tiempo constante. Una sesión existente sin su credencial devuelve 403. Los IDs de cliente deben ser UUID con guiones; se recomienda dejar que el servidor los genere.

`DELETE /api/v1/sesiones/{session_id}` exige esa credencial y elimina checkpoints, escrituras, blobs y autorización. Devuelve 204; sesión inexistente o token incorrecto devuelve 403. Si el mismo hilo está ocupado más allá de la espera configurada devuelve 409 y puede reintentarse. No se borra debajo de una ejecución activa.

Los dos endpoints de evaluación requieren `Authorization: Bearer <INTERNAL_API_TOKEN>`. Sin secreto configurado están deshabilitados (503); sin credencial válida devuelven 401. Nunca distribuir el secreto administrativo a clientes públicos. Las respuestas de consulta y evaluación incluyen `Cache-Control: no-store`. No almacenar tokens en URLs, trazas o almacenamiento compartido.

No cambian las funciones de clasificación, enriquecimiento, selección de documentos, algoritmo FAISS ni los prompts funcionales. En los constructores de OpenAI y embeddings se añaden únicamente timeout y desactivación de reintentos. Los cambios intencionados de contrato y salida se describen a continuación.

## R1. Frontera HTTP de Gradio

**Arranque soportado: `python -m app.ui`. No publicar `demo.launch()` directamente**: ese método omitiría la frontera añadida. Para un servidor ASGI también se admite `python -m uvicorn app.ui:crear_app_gradio --factory --host 127.0.0.1 --port 7860 --workers 1`.

`crear_app_gradio()` monta Gradio bajo `GradioOwnerMiddleware`. Se entrega una cookie de propietario firmada con HMAC, aleatoria, HttpOnly y SameSite=Strict. Su duración es absoluta y la clave es efímera por proceso. En HTTPS debe activarse `GRADIO_COOKIE_SECURE=true`; en HTTP local debe permanecer false. Robar la cookie permite actuar como su propietario: sigue siendo una credencial bearer, no una identidad civil.

Antes de que Gradio recupere estado, cada `session_hash` de JSON, consulta SSE o ruta heartbeat se transforma mediante HMAC con el propietario. Dos navegadores que envían el mismo hash acceden a namespaces distintos. Reenviar el hash interno de otro navegador tampoco selecciona ese estado: se vuelve a transformar bajo el propietario actual. Las peticiones mutantes sin cookie válida, con cookie caducada/alterada o con un Origin ajeno se rechazan. Una cookie caducada requiere volver a abrir la interfaz y comenzar una conversación nueva.

El token de la conversación queda en `gr.State` y no se muestra, pero la garantía de aislamiento procede de la frontera HTTP, no de ese almacenamiento. Los callbacks de nueva conversación y expiración siguen borrando el hilo. Si un reinicio manual encuentra el hilo ocupado, muestra un error controlado y no afirma haberlo eliminado; la expiración diferida queda a cargo del barrido del servicio. API y Gradio mantienen servicios separados, sin continuidad entre canales.

Se bloquean las rutas no necesarias para este piloto: exportación deep-link, archivos, uploads, streaming multimedia, API simple por event_id, reset/cancel externos, monitoring y otras superficies auxiliares indicadas en el middleware. El chat utiliza eventos JSON y cola/SSE, con hasta ocho consultas concurrentes y exclusión por hilo. No se soportan extensiones multimedia, llamadas Gradio Client ni otras rutas sin ampliar antes la política y sus pruebas. Una lectura SSE sin una cola registrada en su namespace se rechaza antes de llegar a Gradio.

Las pruebas HTTP usan el Gradio instalado, dos clientes con cookies independientes, callbacks reales y cola/SSE. No son pruebas de navegador JavaScript completo ni una auditoría exhaustiva del framework. Una actualización de Gradio requiere revisar de nuevo sus rutas y volver a ejecutar estas regresiones. No hay garantía si se publica otra entrada HTTP que evite el middleware.

## R2. Concurrencia y borrado

El registro de sesiones usa un cerrojo de duración corta. Cada sesión tiene su propio cerrojo de ejecución. No se mantiene el cerrojo global durante inferencia, métricas o espera de otro hilo. El barrido toma los cerrojos por sesión sin bloquear: una sesión A activa no impide procesar B ni eliminar C vencida e inactiva.

Después de adquirir un cerrojo se comprueba que sigue siendo el mismo objeto de sesión registrado. Así una operación que esperaba no puede resucitar un hilo borrado o reemplazado. El borrado del mismo hilo se coordina con su ejecución y tiene espera acotada. Los checkpoints de otros hilos permanecen intactos.

`PROVIDER_TIMEOUT_SECONDS=30` configura el timeout de las peticiones de generación y embeddings. `max_retries=0` evita multiplicar llamadas con reintentos automáticos. Estos son límites de transporte del SDK, no una garantía de tiempo total de toda la conversación: puede haber sucesivas llamadas y una respuesta que sigue transmitiendo puede durar más que un timeout de lectura. No se matan threads Python ni se borran checkpoints debajo de una llamada todavía activa. El cierre ordenado espera las operaciones del mismo hilo. Un deadline duro requeriría aislamiento/cancelación adicionales.

## R3. Minimización e información oficial

La redacción sigue siendo **parcial, no anonimización**. Cubre correos, números contiguos de al menos ocho dígitos, algunos identificadores etiquetados y teléfonos internacionales. No detecta exhaustivamente nombres, domicilios, formatos fragmentados o información inferible. No introducir datos personales reales en las pruebas o validación inicial.

Las entradas de usuario se reducen antes del grafo, embeddings y LLM. Las salidas se reducen antes de sus checkpoints e historial. Solo en las salidas se conservan coincidencias exactas con `app/core/official_contacts.py`, una lista controlada por revisión de código y procedente del corpus consular aprobado. No se añade un contacto porque el usuario o el modelo lo llame oficial. Las URLs con parámetros personales adicionales no heredan la autorización de su URL base.

La lista contiene el contacto de consultas observadas y los enlaces documentados de RENIEC, Bookeo y fuentes consulares. Cambiarla exige verificar el documento fuente y revisar el cambio. No se ha contrastado su vigencia en la web en esta fase. El verificador funcional original sigue intacto, incluida su regla que marca correos como observados: preservar el contacto no equivale a cambiar ese verificador.

Persisten posibles falsos positivos/negativos fuera de la lista aprobada. La minimización no controla registros del proxy/APM, retención de OpenAI, snapshots, ni texto ya recibido por el navegador. No constituye una certificación normativa.

## R4. Métricas y fallos de escritura

El nuevo fichero es `data/logs/consultas_metricas.csv`, con fecha, intención de lista cerrada y estado reducido. No contiene preguntas, respuestas, fuentes en texto libre, IDs de sesión ni credenciales. Las columnas históricas de texto quedan vacías o con `[]`; el resumen por fuentes pierde ese detalle. La consulta de registros se limita a 1–100 filas.

Un `OSError` al registrar métricas (incluido PermissionError por permisos o bloqueo de archivo en Windows, o disco lleno) no invalida una respuesta ya producida ni elimina sus checkpoints. La consulta continúa con 200 y `X-Metrics-Status: unavailable`. Con éxito devuelve `X-Metrics-Status: ok`. Solo se emite una advertencia fija sin excepción, ruta ni datos personales. El cliente Python recibe `metricas_registradas` como booleano. El JSON público de consulta no cambia.

Los fallos de ejecución del grafo siguen borrando checkpoints parciales y revocando la sesión. La excepción de métricas es deliberadamente más acotada: no oculta fallos arbitrarios de programación. La política no asegura disponibilidad del almacenamiento ni recupera métricas perdidas.

## R5. Retención y vencimiento durante una consulta

El TTL es **absoluto**, desde la creación: usar una sesión no lo renueva. El barrido periódico y las comprobaciones en acceso/salida eliminan hilos vencidos mediante `InMemorySaver.delete_thread()`, que elimina storage, writes y blobs. Dentro del TTL se conservan los checkpoints; seis turnos funcionales no significan seis checkpoints.

Si el TTL vence durante una operación, al terminar se descarta el resultado, se elimina todo el hilo y se responde **410**, sin `X-Session-Token`. El cliente debe iniciar otra conversación sin ID/token antiguos. Gradio descarta el estado/credencial vencidos y pide recargar la interfaz; la cookie de propietario puede haber caducado también. Una continuación posterior con la credencial revocada recibe 403. No se rota ni renueva silenciosamente la credencial. Esta política puede descartar trabajo o consumo del proveedor ya realizado.

El barrido no elimina una ejecución activa. Su limpieza queda diferida hasta su finalización, pero no bloquea el borrado de otras sesiones. El cierre elimina los hilos restantes. No se promete borrado forense de RAM/swap ni una cota temporal estricta durante una operación externa bloqueada.

## Configuración y despliegue

| Variable | Default | Uso |
|---|---|---|
| `INTERNAL_API_TOKEN` | Ausente | Secreto administrativo fuerte. Sin él se deshabilita evaluación. |
| `SESSION_TTL_SECONDS` | 1800 | Duración absoluta; entre 1 y 86400. |
| `SESSION_CLEANUP_INTERVAL_SECONDS` | 30 | Barrido; entre 1 y 300. |
| `SESSION_MAX_COUNT` | 256 | Capacidad simultánea; entre 1 y 10000. |
| `SESSION_WAIT_SECONDS` | 5 | Espera del mismo hilo antes de 409; mayor que 0 y hasta 30. |
| `PROVIDER_TIMEOUT_SECONDS` | 30 | Timeout de transporte; mayor que 0 y hasta 120. |
| `GRADIO_COOKIE_SECURE` | false | true detrás de HTTPS; false exclusivamente para HTTP local. |

Sin dependencias nuevas ni cambios de versiones. No se modifica ningún `.env` privado. Inyectar secretos con el mecanismo local o del despliegue; no publicarlos, imprimirlos ni ponerlos en scripts versionados.

Ejecutar **un worker y una réplica por canal**. Reiniciar revoca cookies y sesiones; no hay almacenamiento compartido entre procesos. No escalar sin sustituir conjuntamente registro, coordinación, cookies y checkpoints. Las cuotas por cliente, TLS y protección del proxy siguen siendo necesarias. El límite de sesiones no limita por sí solo todos los checkpoints o peticiones dentro del TTL.

Antes de desplegar, detener las instancias antiguas. Inventariar y eliminar/custodiar mediante una política autorizada `consultas_log.csv`, CSV de evaluación, notebooks con salidas y copias anteriores. No se destruyen archivos previos automáticamente. No copiarlos al nuevo fichero de métricas. El lector nuevo no expone las columnas de texto aunque se le proporcione explícitamente un fichero antiguo.

## Windows PowerShell y Conda

Desde la raíz del repositorio, con Conda instalado:

```powershell
conda create -n tfm-piloto python=3.11 -y
conda activate tfm-piloto
python -m pip install -r requirements.txt
$env:GRADIO_ANALYTICS_ENABLED = "False"
$env:PYTHONDONTWRITEBYTECODE = "1"
python -B -m pytest -q -p no:cacheprovider
```

No se necesita OpenAI para esa suite. Para ejecutar servicios en terminales independientes, activar el mismo entorno y usar:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
# En otra terminal Conda:
python -m app.ui
```

Para la funcionalidad LLM/RAG real, configurar localmente la clave OpenAI y generar el índice según el README; no imprimir la clave. Configurar el secreto administrativo si se van a consultar métricas. La prueba marcada como fallo Windows simula PermissionError; no certifica una ejecución nativa en Windows. Las pruebas de esta corrección se ejecutan en Linux con Python 3.11; la validación Windows/Conda queda como paso manual pendiente.

## Linux

Con Python 3.11 y dependencias ya instaladas, usar `python` del entorno activo. Si se prepara desde cero, `requirements.txt` es UTF-16 e incluye pywinpty de Windows. Generar una copia temporal para Linux sin alterar el archivo versionado:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -c "from pathlib import Path; s=Path('requirements.txt').read_text(encoding='utf-16'); Path('/tmp/tfm-requirements-linux.txt').write_text('\n'.join(x for x in s.splitlines() if not x.lower().startswith('pywinpty=='))+'\n', encoding='utf-8')"
python -m pip install -r /tmp/tfm-requirements-linux.txt
export GRADIO_ANALYTICS_ENABLED=False
export PYTHONDONTWRITEBYTECODE=1
python -B -m pytest -q -p no:cacheprovider
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
# En otra terminal con el entorno activado:
python -m app.ui
```

Las seis pruebas `integration` siguen separadas y requieren proveedor e índice reales. Se seleccionan explícitamente con `python -m pytest -m integration`. No se ejecutan ni se certifican durante esta fase. Las pruebas deterministas usan datos ficticios, archivos temporales, grafo/checkpointer reales y proveedor simulado cuando corresponde; no miden exactitud factual del LLM ni calidad semántica del RAG.

## Evidencia de esta corrección

Ejecutado en Linux/Python 3.11: **55 pruebas aprobadas y 6 de integración excluidas**, sin servicios externos ni claves reales. Incluye HTTP real mediante ASGI/TestClient con dos navegadores lógicos y cola/SSE de Gradio, exclusión por hilo y concurrencia A/B/C, borrado sin resurrección, contactos oficiales, PermissionError/disco lleno simulados, caducidad con reloj simulado y descarte del estado vencido en Gradio. Se observaron advertencias de deprecación de dependencias; no fallos.

La comparación AST contra `8c08972` confirma que las funciones de clasificación, enriquecimiento, selección documental, generación/prompt y verificación permanecen idénticas. El algoritmo de recuperación no cambia: las modificaciones de embeddings se limitan al timeout y ausencia de reintentos en sus constructores. `git diff --check` correcto. No se ejecutó Windows nativo, navegador JavaScript completo ni OpenAI real; el dictamen es preparación para validación local, no aprobación de producción ni ausencia garantizada de defectos.

## P2: Enter y botón simultáneos en una conversación

La concurrencia global de hasta ocho eventos se mantiene para permitir que otros navegadores sigan operando. `ConversationBlocks` añade exclusión asíncrona por `SessionState` HTTP, ya aislado por la cookie y el namespace HMAC de R1. No hay un cerrojo global adicional ni se usa un UUID elegido por el cliente como autorización.

Se serializa **todo `process_api`**: lectura de `gr.State`, ejecución del callback y actualización de salidas. Bloquear solo el callback no basta, porque Gradio puede haber leído previamente el mismo estado inicial sin token para dos eventos distintos. El cerrojo reside como atributo del contenedor `SessionState`, no dentro del valor serializable de `gr.State`, y sigue el ciclo de vida de ese contenedor, sin un registro global de cerrojos por conversación.

El historial visual autoritativo se conserva ahora en `gr.State`, junto al identificador y la credencial. El parámetro Chatbot de entrada se mantiene por compatibilidad del evento, pero no sustituye ese historial: dos peticiones encoladas pueden enviar ambas una copia visual antigua. El historial nuevo contiene únicamente el texto reducido que ya construye el callback. Reiniciar o descartar el estado vencido limpia también esta copia. Las protecciones R1–R5 y los límites de retención no se sustituyen.

Las regresiones reproducen la carrera desactivando solo la nueva serialización y comprueban su corrección mediante dos peticiones HTTP simultáneas, además de eventos reales de cola/SSE para los triggers del botón y Enter. Verifican una única credencial/conversación, ambos turnos en orden, continuidad del historial pese a snapshots vacíos y progreso de otro navegador mientras la primera consulta está bloqueada. También se comprueba que reiniciar no reutiliza el historial anterior.

No se deduplican mensajes: si el cliente envía dos eventos válidos, se procesan como dos turnos, aunque sus textos fueran iguales. Se mantiene el límite global de ocho eventos; no se promete concurrencia ilimitada ni equidad frente a abuso. La extensión usa el ciclo `process_api` de Gradio 6.19.0 instalado: al actualizar Gradio hay que ejecutar nuevamente las pruebas HTTP, cola/SSE y seguridad. La aplicación continúa soportada en un solo proceso/event loop por canal. No se ha realizado una prueba de navegador JavaScript completo ni una nueva ejecución nativa en Windows.

Validación P2 ejecutada en Linux/Python 3.11: **59 pruebas aprobadas y 6 de integración excluidas**, sin OpenAI real. Incluye cuatro casos nuevos: reproducción controlada sin el cerrojo, corrección con HTTP simultáneo, historial obsoleto/reinicio y simultaneidad a través de cola/SSE. Se ejecutan también todas las regresiones R1–R5. El aislamiento de pruebas reinicia el enlace de la cola de Gradio a la app ASGI para no reutilizar el StateHolder de una aplicación de prueba anterior; no se relajan las aserciones de seguridad. `git diff --check` correcto.
