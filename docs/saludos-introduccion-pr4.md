# Saludos y consultas introductorias — PR #4

Base: f937249. Rama: feature/dni-mayor-ampliacion. Fecha: 29/10/2026.

## Causa y reproducción

El grafo enviaba todos los mensajes al clasificador material. Una introducción con DNI abría una aclaración de operación; un saludo sin DNI pedía indicar el trámite. En una conversación activa, una cortesía podía volver a recuperar el procedimiento anterior.

Antes de modificar producción se ejecutaron seis casos nuevos: **6 fallidos**. Después pasaron los seis. Una primera ejecución ampliada detectó además tres fallos nuevos: saludo sin tilde, pasaportes en plural no reconocido por OTROS y expectativa demasiado amplia de clasificación civil sin referencia a DNI. Se corrigieron los dos primeros; el caso documental se especificó con DNI y se añadió por separado una prueba que conserva el resultado prudente del clasificador original cuando falta esa referencia. No se eliminó ninguna regresión anterior.

## Implementación por archivo

- `app/graph/social.py`: reconocimiento determinista por coincidencia completa de cortesías e introducciones acotadas. No usa reloj, proveedores ni hechos administrativos. El contenido residual no reconocido sigue al clasificador. Conserva el saludo escrito por el ciudadano, con ortografía normalizada.
- `app/graph/dni_graph.py`: bifurcación temprana social hacia un nodo terminal sin RAG/OpenAI/verificador documental. Fuentes y fragmentos vacíos, intención pública `general`, verificación `ok` (cortesía, no validación factual), estado interno `interaccion_social`. Conserva íntegramente el contexto canónico. En mensajes materiales, añade únicamente un saludo breve después del control factual; no reescribe el contenido documental.
- `app/graph/state.py`: respuesta social temporal, vaciada expresamente en cada turno material para evitar reutilización del checkpoint anterior.
- `app/graph/classification.py`: acepta también `pasaportes` en el detector existente de procedimientos ajenos. No autoriza fuentes ni añade un procedimiento.
- `tests/test_social_turns.py`: 33 casos nuevos, incluyendo proveedores prohibidos, sesiones independientes, contexto idéntico antes/después, rechazo persistente, aclaración de edad y continuación posterior, mensajes mixtos, negaciones e introducción real.

No se cambian servicios de sesión, endpoints, validación pública, cookies, privacidad, tarifas, reglas de integridad, TXT ni FAISS. Las cortesías ocupan un turno del historial limitado existente; los hechos materiales permanecen en el contexto canónico. Las métricas conservan el contrato público `general` y fuentes vacías, sin una categoría pública nueva.

## Ejemplos completos de respuestas sociales

Consulta: «Buenas noches».

Antes: «Para poder orientarle, Indique si desea orientación sobre DNI y cuál es el trámite solicitado.»

Después: «¡Buenas noches! Soy el asistente virtual de orientación sobre trámites de DNI del Consulado General del Perú en Turín. ¿En qué puedo ayudarle?»

Consulta: «Buenas noches, ¿puedo hacer acá consultas respecto a trámites de DNI en el Consulado de Perú en Turín?».

Antes: «Para poder orientarle, Indique si es su primer DNI o la renovación de un DNI que ya tuvo.»

Después: «¡Buenas noches! Sí, puede consultar información sobre los trámites de DNI disponibles, sus requisitos, citas y seguimiento. Ofrezco orientación; no realizo trámites, no emito documentos ni reservo citas por usted. ¿Qué desea consultar?»

Consulta: «Gracias por la información».

Antes: «Para poder orientarle, Indique si desea orientación sobre DNI y cuál es el trámite solicitado.»

Después: «Con gusto. Si necesita alguna otra orientación sobre trámites de DNI, puede consultarme.»

Ejemplos obtenidos con proveedores simulados, no de una nueva conversación real con OpenAI.

## Límites

El reconocimiento es deliberadamente acotado, no un clasificador general de conversación social. Expresiones fuera de sus formas completas siguen al flujo material y pueden pedir una aclaración prudente. Una solicitud civil sin DNI/contexto suficiente conserva las aclaraciones existentes: esta intervención no amplía inferencias de alcance. `ok` para cortesías significa que no se hicieron afirmaciones documentales; no prueba exactitud administrativa. No se ejecutó Windows nativo ni OpenAI real. Se requiere revisión visual local en Gradio.

## Windows / Conda

```powershell
git fetch origin
git switch feature/dni-mayor-ampliacion
git pull --ff-only origin feature/dni-mayor-ampliacion
conda activate tfm-piloto
$env:GRADIO_ANALYTICS_ENABLED="False"
$env:PYTHONDONTWRITEBYTECODE="1"
python -B -m pytest -q --tb=short -p no:cacheprovider
python -m app.ui
```

No reconstruir FAISS por este cambio. Probar una sesión nueva con la introducción original, una renovación con saludo, «Hola de nuevo» y una repregunta de coste; abrir otro navegador para comprobar independencia. No editar credenciales.

## Resultado ejecutado

Linux, Python 3.11.17, entorno `.venv` existente, variables OpenAI retiradas del proceso y proveedores simulados: **900 passed, 6 deselected, 12 warnings in 13.78s**. Son las 867 regresiones anteriores más 33 nuevas. Las seis excluidas están marcadas `integration`; no se ejecutaron. Los avisos son de dependencias. `git diff --check` sin errores y `git diff f937249 -- data/raw` vacío. No se reconstruyó el índice. Los casos sociales sustituyen tanto la búsqueda semántica como la exacta por funciones que fallan si se invocan, y comprueban que el proveedor LLM simulado no recibió prompts.
