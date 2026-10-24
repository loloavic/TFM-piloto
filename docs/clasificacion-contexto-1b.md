# Fase 1B.1–1B.2: clasificación de DNI y continuidad

## Base y alcance

Rama `fix/dni-classification-context`, creada desde `main` en `f6d9c333bf1e3966086fb3aed4d16a9a9aac6359`. Se verificó la integración del PR #1 y la presencia de su último commit `3c62414` en la ascendencia. No se modifican seguridad, sesiones, cookies, concurrencia, credenciales, dependencias ni el catálogo documental.

Se mantienen los mismos nodos y aristas LangGraph, FastAPI, Gradio, OpenAI y FAISS. La recuperación vectorial y sus parámetros no cambian. El verificador existente y el prompt funcional de generación se conservan. La respuesta de aclaración/abstención determinista sí se ajusta, sin añadir requisitos, importes ni enlaces.

## Defectos confirmados y causas

1. La renovación se asignaba a menores sin identificar la edad del titular. «Mi hijo» podía referirse a un adulto. No había representación de un trámite identificado pero sin documentación.
2. La simple aparición de pasaporte, matrimonio u otra palabra tenía prioridad absoluta. Confundía documentos de apoyo y expresiones negadas con el procedimiento solicitado. La búsqueda por subcadenas tampoco delimitaba bien palabras.
3. Las negaciones se cubrían con unas pocas frases literales y no se separaban de correcciones positivas posteriores.
4. `intencion` era simultáneamente procedimiento, tema del turno y memoria activa. «¿Cuánto demora?» lo cambiaba a seguimiento y el coste/cita posterior heredaba ese cambio.
5. El enriquecimiento de preguntas sobre plazo insertaba términos de seguimiento RENIEC de forma automática, aunque el procedimiento seguía siendo renovación o primera inscripción.

Antes de corregir, cinco casos añadidos de auditoría fallaron sobre la implementación integrada. La comparación local con la función de `f6d9c33` también ejecutó la secuencia de cuatro turnos y obtuvo renovación → seguimiento → seguimiento → seguimiento. Con la corrección conserva renovación en los cuatro turnos.

## Modelo de estado y compatibilidad

`app/graph/classification.py` concentra reglas deterministas normalizadas, con palabras delimitadas y expresiones negadas separadas de sus afirmaciones. No incorpora un segundo clasificador LLM ni requiere conexión de red.

| Campo | Significado |
|---|---|
| `tramite_actual` | Identificación persistente del procedimiento, incluso si no está documentado. |
| `operacion_dni` | Renovación, primera vez, título explícito no documentado o todavía sin aclarar. |
| `tipo_consulta` | Requisitos, coste, plazo, cita, seguimiento u otra información; se calcula por turno. |
| `contexto_solicitante` | Únicamente grupo de edad y destinatario genérico. No guarda nombre, DNI, edad exacta ni otros identificadores estructurados. |
| `tramite_documentado` | Si la identificación corresponde a una de las tres rutas del corpus existente. |
| `estado_documental` | Disponible, no documentado, pendiente de aclaración, fuera de alcance o sin evidencia recuperada. |
| `requiere_aclaracion`, `motivo_aclaracion` | Decisión explícita y motivo de la pregunta de aclaración. |
| `historial` | Conserva el límite funcional existente de seis turnos. Los checkpoints siguen bajo el TTL y borrado de Fase 1A. |

Los códigos internos `dni_adulto_renovacion`, `dni_adulto_primera_vez` y `dni_duplicado` **no habilitan nuevos procedimientos**. Sirven para conservar lo identificado, abstenerse y no entregar documentación de menores a un adulto. Reconocer el término «duplicado» únicamente permite abstenerse: no afirma que el consulado ofrezca ese servicio ni añade documentación. Las identificaciones sin edad tampoco habilitan requisitos de renovación/primera inscripción. Si se conoce operación pero no edad, se pregunta la categoría de edad; si falta operación se distingue primer DNI de renovación.

El contexto procede del texto ya reducido por los controles existentes. Solo se deriva la categoría necesaria para seleccionar el corpus; no se introduce almacenamiento adicional de datos personales exactos. La redacción de texto libre continúa siendo parcial, con las limitaciones documentadas de Fase 1A.

`intencion` mantiene los valores públicos anteriores como adaptador hacia los nodos existentes. Puede ser `dni_consulta_estado` para seleccionar documentación de seguimiento sin reemplazar una renovación activa. En una pregunta posterior sobre coste vuelve a la ruta del procedimiento activo. Adultos no documentados y ambigüedades usan `general`, pero quedan diferenciados en el estado y en la respuesta al ciudadano.

No se cambia el esquema JSON público ni los contratos de autorización. Cambia intencionadamente la clasificación de consultas insuficientes: «renovar el DNI de mi hijo» ya no presume minoría de edad. Se debe responder «menor» o «adulto», o indicar la edad/categoría en la consulta inicial. Una nueva conversación o el borrado autorizado no conserva el contexto anterior. Los despliegues deben reiniciar los procesos para cargar la nueva versión; no se migran checkpoints de procesos antiguos.

## Antes y después

| Entrada o secuencia | Antes | Ahora |
|---|---|---|
| Adulto que quiere renovar su DNI | Renovación de menor | Identifica renovación de adulto; abstención por falta de documentación. |
| DNI de hijo sin edad | Presume menor | Aclara categoría de edad. |
| Pasaporte negado y renovación del DNI de menor | Fuera de alcance | Renovación de menor. |
| Fotos tamaño pasaporte para DNI | Fuera de alcance | Se trata como requisito/documento de apoyo del DNI. |
| «No es la primera vez; ya tiene DNI» con titular menor | Dependía de coincidencias literales | Renovación; no se toma primera vez como afirmativa. |
| Renovación de hijo de 10 años → plazo → coste → cita | Cambia y permanece en seguimiento | Conserva procedimiento; cambia únicamente el tema. |
| Seguimiento explícito dentro de una renovación → coste | Se pierde renovación | Usa fuentes de seguimiento en ese turno y conserva la renovación para coste. |
| Peticiones contradictorias o varios procedimientos | Podía elegir una categoría | Aclara antes de recuperar o generar. |
| Procedimiento reconocido pero sin fragmentos | Abstención genérica sin indicador documental | Conserva identificación y marca `sin_evidencia`; no invoca el generador. |

Las edades de acompañantes no se asignan al titular. El DNI del progenitor solicitado como requisito no lo convierte en el nuevo titular. Los cambios de titular explícitos no heredan por inercia una operación que no se ha solicitado para la nueva persona.

## Pruebas y preservación de Fase 1A

La suite nueva combina casos de clasificación con ejecución del grafo/checkpointer reales, recuperación simulada a partir de los tres textos del corpus y un generador simulado. Comprueba negaciones, documentos de apoyo, ambigüedades, cambio explícito, aislamiento, borrado/reinicio, fuentes seleccionadas, contexto mínimo, límite de historial y una secuencia HTTP completa con la credencial de sesión existente.

Las pruebas previas de seguridad conservan todas sus aserciones. Dos entradas de prueba se precisan con «menor» o «DNI» para que sigan ejerciendo las rutas de proveedor/contacto que verifican. Cuatro entradas de las pruebas de integración también explicitan «menor». No se deshabilitan controles ni se sustituyen resultados esperados de seguridad por éxitos triviales. Los casos ahora ambiguos se cubren expresamente como aclaraciones, no se eliminan.

Las seis pruebas con proveedor e índice reales permanecen marcadas como `integration` y no se ejecutan en la suite determinista. No se han usado datos personales reales ni claves OpenAI reales. El prompt funcional y el verificador se comparan contra la base integrada para detectar cambios no autorizados.

La abstención de adulto utiliza `general` para conservar compatibilidad. Su texto contiene una indicación orientativa «Por favor, consulte los canales oficiales», compatible con las heurísticas existentes del verificador. No se presenta `verificacion=ok` como certificación factual.

## Ejecución local

No se añaden dependencias ni variables de entorno. Desde la raíz y con Python 3.11/Conda activo en Windows PowerShell:

```powershell
conda activate tfm-piloto
$env:GRADIO_ANALYTICS_ENABLED = "False"
$env:PYTHONDONTWRITEBYTECODE = "1"
python -B -m pytest -q -p no:cacheprovider
```

En Linux, con el entorno existente activado:

```bash
GRADIO_ANALYTICS_ENABLED=False PYTHONDONTWRITEBYTECODE=1 \
  python -B -m pytest -q -p no:cacheprovider
```

Los servicios siguen arrancándose con `python -m app.ui` y `python -m uvicorn app.main:app --workers 1`, según la guía de seguridad. No publicar Gradio evitando su frontera HTTP. La validación realizada aquí es en Linux; no se certifica Windows nativo ni navegador JavaScript completo.

## Riesgos residuales

Las reglas no constituyen comprensión lingüística exhaustiva: elipsis, múltiples titulares, correcciones complejas, faltas ortográficas y nuevas paráfrasis pueden requerir reglas adicionales o nuevas aclaraciones. El tema es una etiqueta única y se prioriza cuando una consulta contiene varias preguntas; el texto original reducido sigue disponible para el generador. No se mide precisión estadística con estos ejemplos elegidos.

El criterio de edad se usa para enrutar el corpus, no como validación legal ni comprobación de identidad. Si hay contradicción detectada se solicita aclaración. Los metadatos no garantizan vigencia o suficiencia normativa de los documentos; no se han vuelto a validar tarifas, horarios o fuentes oficiales en línea.

Persisten las limitaciones ya auditadas del verificador factual, la relevancia semántica y las posibles respuestas incompletas del LLM. Las pruebas simuladas no demuestran calidad real de generación/embeddings. No se han ampliado procedimientos, tasas ni requisitos; esa ampliación necesitaría documentación aprobada y otra fase de evaluación.


## Resultado ejecutado

**132 pruebas aprobadas y 6 de integración excluidas**, en Linux con Python 3.11, sin claves OpenAI reales. Son 73 casos nuevos respecto a la base de 59 pruebas deterministas de Fase 1A. Se ejecutaron las regresiones de seguridad R1–R5 y Enter/botón, además de la suite nueva de clasificación y grafo. Las advertencias proceden de dependencias existentes; no hubo fallos en la ejecución final.

Comando ejecutado: `GRADIO_ANALYTICS_ENABLED=False XDG_CACHE_HOME=/tmp/tfm-cache PYTHONDONTWRITEBYTECODE=1 env -u OPENAI_API_KEY -u TFM_OPENAI_API_KEY .venv/bin/python -B -m pytest -q --tb=short -p no:cacheprovider`. `git diff --check` correcto. Comparación AST: verificador, construcción del grafo, historial y envoltorio de minimización intactos; literal del prompt de generación idéntico. Comparación Git: seguridad, UI/API, servicios, FAISS, corpus, credenciales y dependencias intactos.

La implementación está preparada para revisión técnica y posterior validación local. No equivale a una validación con modelos reales, comprobación normativa del corpus, precisión lingüística general ni ejecución nativa en Windows.
