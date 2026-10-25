# Cierre de aclaraciones por motivo pendiente

Base: `3aa8b55`, PR #2, rama `fix/dni-classification-context`.

## Defecto confirmado y reproducción

El bloque de resolución aceptaba como respuesta genérica una operación **o** un titular. El motivo `titular` no tenía un criterio propio. Además, «ahora» junto con una operación podía omitir la aclaración como supuesto cambio inequívoco. La herencia conservaba el contexto del menor anterior, aunque el ciudadano hubiera introducido explícitamente un hijo menor y una hija adulta.

Antes de modificar el clasificador se ejecutaron dos pruebas del grafo con recuperador y LLM simulados, sobre esta secuencia:

1. «Necesito renovar el DNI de mi hijo de 10 años».
2. «Quiero renovar el DNI de mi hijo menor y de mi hija adulta».
3. «Quiero renovar el DNI» o «Ahora quiero renovar el DNI».

**Ambas fallaron sobre `3aa8b55`**: `requiere_aclaracion` pasaba a falso sin haber elegido titular. Las mismas pruebas ahora comprueban que la intención sigue siendo general, se pregunta por el titular, las fuentes están vacías y no aumenta el número de llamadas al recuperador ni al generador.

## Corrección estructural

No se añade un modelo ni se cambia el esquema de estado. Se reutilizan `decision.faltantes` y `decision.contradicciones` para conservar **todos** los motivos pendientes, y `motivo_aclaracion` para elegir una única pregunta. `requiere_aclaracion` sigue siendo el bloqueo documental.

- `_motivos_pendientes` reúne las dudas que siguen abiertas.
- `_funcion_documento` detecta una confirmación explícita del papel del documento, separada de su operación. No acredita capacidad legal ni autoriza representación.
- `_resuelve_motivos` declara qué evidencia permite resolver cada dimensión.
- `clasificar` elimina solo los motivos resueltos, incorpora dudas nuevas y confirma únicamente si el conjunto restante está vacío. La selección de la pregunta es estable: titular, documento, tenencia previa, contradicción, operación, edad y ámbito.

Cuando hay una duda sobre titular, la propuesta se evalúa **sin heredar el contexto personal anterior**. Mientras siga abierta, `contexto_solicitante` queda vacío. El último `tramite_actual` puede conservarse como referencia histórica; nunca habilita recuperación si se requiere aclaración. Confirmar renovación conserva esa operación, pero no identifica al beneficiario.

Si varias dudas aparecen juntas, se resuelven de forma incremental. Por ejemplo, al elegir primero a la hija adulta se conserva ese contexto mínimo y se sigue preguntando por la operación; al confirmar primero renovación se conserva la operación y se sigue preguntando por el titular. Las categorías de edad aisladas no seleccionan automáticamente una persona entre varias.

La función de un documento y la operación previamente confirmada se mantienen independientes: aclarar «como documento de apoyo» no obliga a repetir una renovación conocida. Las expresiones de rol no se confunden con una petición nueva de requisitos, por lo que se conserva el tema coste/plazo que estaba pendiente.

## Matriz de condiciones de resolución

| Motivo | Evidencia suficiente para esa dimensión | Respuestas que no bastan |
| --- | --- | --- |
| Titular | Referencia explícita a un beneficiario sin conflicto, como «es para mi hija adulta» o «es para mi hijo menor» | Solo renovar/primer DNI, «ahora renovar», edad aislada o una mención de acompañante |
| Operación | Operación afirmativa identificable y sin conflicto entre operaciones | Identificar únicamente al titular o confirmar solo su edad |
| Función documental | Confirmar apoyo o DNI objeto del trámite; una solicitud completa con operación y titular inequívocos también puede sustituir la duda documental anterior | Repetir únicamente una operación. Confirmar que es el DNI del titular sin identificarlo deja pendiente al titular |
| Tenencia previa / procedimiento | Evidencia suficiente sobre DNI previo o primera inscripción, o una rectificación procedimental inequívoca | Identificar solo a la persona, preguntar coste o responder un «sí» a una disyuntiva |
| Edad | Categoría de edad explícita, sin contradicción; si además sigue pendiente el titular, esa duda continúa abierta | Confirmar únicamente renovación o primera inscripción |
| Ámbito | Solicitud DNI identificada y sin conflicto de ámbito | Información sobre personas sin identificar el objetivo |
| Contradicción general | Procedimiento identificable y sin conflictos actuales | Solo una mención de persona |

**Resolver una dimensión no autoriza recuperación mientras quede cualquier otra duda material.** El criterio local de operación puede cumplirse mientras el titular continúa pendiente; la decisión global sigue bloqueada.

Un cambio inequívoco de procedimiento o titular puede sustituir el objetivo anterior si aporta los datos suficientes. Una operación sola, aunque incluya «ahora», no evita una duda de titular. Un cambio explícito hacia consulta genérica de estado DNI abandona la selección de titulares y no traslada la operación en disputa: usa únicamente la fuente genérica de seguimiento. Cambiar de tema a pasaporte abandona la aclaración y conserva la abstención fuera de alcance.

## Matriz ejecutada A–G

| Secuencia | Comprobación | Resultado |
| --- | --- | --- |
| A: titular ambiguo → operación sola | Sigue pendiente titular; operación retenida; cero recuperación/generación adicional | Aprobado, con y sin «ahora» |
| B: titular ambiguo → hija adulta | Renovación adulta identificada; sin fuentes ni generación documental; abstención explícita | Aprobado |
| C: titular ambiguo → hijo menor | Renovación menor; solo fuente `dni_menor_renovacion.txt`; tema coste y credencial conservados | Aprobado |
| D: operación ambigua → titular solo | Permanece operación pendiente; después se resuelve sin repetir titular | Aprobado, adulto y menor |
| E: primera inscripción → DNI vencido → confirmación | Un titular solo no cierra la contradicción; tenencia previa o nunca haber tenido DNI selecciona la fuente correspondiente | Aprobado |
| F: cambio inequívoco | Primer DNI del menor o renovación propia de adulto se identifican sin aclaración innecesaria | Aprobado |
| G: cambio de tema | Pasaporte sale del ámbito; seguimiento DNI usa su fuente genérica sin heredar el titular en disputa | Aprobado |
| Dudas simultáneas | Operación y titular se resuelven en ambos órdenes, sin documentos durante el paso parcial | Aprobado |
| Documento / consulta pendiente | Operación sola no confirma función; apoyo explícito retoma coste; documento propio sin dueño mantiene duda de titular | Aprobado |
| Información aún incompleta | Edad sola no resuelve titular; titular sin edad deja únicamente edad pendiente | Aprobado |

Las **225 pruebas anteriores** se conservan sin modificar sus aserciones, incluidas P2.1–P2.6, privacidad, autorización, sesiones, TTL/borrado, memoria y concurrencia. Se añaden **21 casos**. Las nuevas secuencias usan el grafo/checkpointer real y recuperación/LLM simulados; comprueban intención, estado, fuentes, respuesta de aclaración/abstención y llamadas externas simuladas.

Comando ejecutado:

```bash
GRADIO_ANALYTICS_ENABLED=False XDG_CACHE_HOME=/tmp/tfm-cache PYTHONDONTWRITEBYTECODE=1 \
  env -u OPENAI_API_KEY -u TFM_OPENAI_API_KEY \
  .venv/bin/python -B -m pytest -q --tb=short -p no:cacheprovider
```

**246 aprobados, 6 de integración excluidos, 12 advertencias de dependencias, 6,09 s**, Linux/Python 3.11.17. No se usaron claves OpenAI reales ni servicios externos. `git diff --check` correcto. La comparación Git contra la base confirma que API/UI, estado, seguridad, sesiones, privacidad, concurrencia, grafo, prompts, verificador, FAISS, corpus y dependencias no cambian.

## Compatibilidad, despliegue y límites

Solo cambia `app/graph/classification.py`, se amplía `tests/test_dni_classification_context.py` y se actualiza documentación. No hay nuevas variables, datos personales, esquemas de persistencia ni dependencias. Siguen vigentes las instrucciones [Windows/Conda y Linux](ambiguedades-contexto-1b.md#windowsconda-y-despliegue). Como antes, reiniciar el proceso al desplegar elimina las sesiones en memoria; no se modifica esa política.

Preparado para repetir validación local en Windows/Conda con Python 3.11. **No se ha ejecutado Windows nativo ni integración OpenAI/FAISS real** en este trabajo. La suite determinista no demuestra comprensión general del español ni calidad factual de las respuestas de un modelo real.

Persisten riesgos de interpretación de referentes y paráfrasis no cubiertas. No se guardan identidades ni un censo de titulares: las señales categóricas pueden requerir preguntas conservadoras en casos más complejos. Una consulta puede necesitar varias aclaraciones, una por turno, si faltan varios datos. La cola de preguntas sigue siendo un único tema pendiente; al cambiar de tema no se conserva una lista de múltiples solicitudes. El verificador factual continúa pendiente de Fase 1B.3.

El PR #2 debe permanecer sin fusionar y someterse a revisión. Actualizar su rama no implica aprobar su integración.
