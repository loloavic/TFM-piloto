# PR #4: estabilización de viudez y disposiciones generales

> Evidencia histórica de su entrega. El estado consolidado, pruebas y correcciones posteriores se describen en [integridad y métricas del PR #4](integridad-metricas-pr4.md). Los resultados de este informe corresponden a su versión.


27 de octubre de 2026. Base inicial `e19d9f8`, rama `feature/dni-mayor-ampliacion`.

## Fase A — Viudez y recuperación

### Reproducción y causa

Antes de modificar producción, cinco regresiones dieron **cuatro fallos y un acierto**. «No» directo resolvía la dimensión pendiente; las tres negativas ampliadas no lo hacían y no existía diagnóstico de la regla faltante.

El reconocedor de apellido solo manejaba expresiones con `recuperar` o sí/no literal. «No necesito cambiar mi apellido» además coincidía con una negación genérica de modificación y podía borrar el cambio civil. Ahora las negativas ampliadas se procesan como evidencia transitoria del apellido en un contexto civil de divorcio/viudez; no son negación de todo el procedimiento. Las respuestas binarias siguen resolviendo exclusivamente la dimensión pendiente. No se guarda el apellido real ni el texto de esa evidencia.

La selección de documentos exige todas las reglas del plan. El top‑10 semántico puede omitir una regla pertinente aunque exista en el índice. Se reproduce esta omisión con proveedor simulado y se comprueba un reintento específico. **No se ha inspeccionado el índice de Windows:** no puede afirmarse si su abstención concreta se debió al top‑10, a un índice obsoleto, a una regla ausente o a un marcador incompleto.

### Archivos

- `adult_context.py`: negativas y afirmativas ampliadas; decisiones opuestas generan conflicto; no confundir apellido con rechazo de la modificación civil.
- `classification.py`, `state.py`: categoría transitoria `respuesta_apellido`; lista diagnóstica `reglas_faltantes` en el estado del grafo, sin identificadores de ciudadanos.
- `dni_graph.py`: selección por archivo/regla intacta; reintento por cada regla autorizada que falte tras la consulta inicial. Cada reintento pide diez resultados y vuelve a filtrar; no incorpora fragmentos ajenos. El bucle recorre un conjunto inicial finito, no reintenta indefinidamente. Si falta alguna regla, descarta el conjunto incompleto y conserva abstención. Reintentos pueden aumentar latencia/coste de embeddings; se mantienen timeouts y aislamiento existentes.
- `verificar_respuesta`: una salida segura con `estado_documental=sin_evidencia` se marca `abstencion_documental`, con los identificadores técnicos de reglas faltantes cuando existen. Los borradores reemplazados por el control determinista siguen siendo `observada`. Así `ok` no oculta una recuperación incompleta.
- `test_widow_stabilization.py`: quince casos nuevos. Conserva condiciones, actas con observación pendiente, fuentes completas/incompletas/ausentes, corrección tras contradicción, recuperación mediante reintento, cambios de titular y sesiones independientes.

### Resultado ejecutado de Fase A

Linux, Python 3.11.17; proveedores simulados:

```bash
GRADIO_ANALYTICS_ENABLED=False XDG_CACHE_HOME=/tmp/tfm-cache PYTHONDONTWRITEBYTECODE=1 env -u OPENAI_API_KEY -u TFM_OPENAI_API_KEY .venv/bin/python -B -m pytest -q --tb=short -p no:cacheprovider
```

**503 aprobadas, 6 de integración excluidas, 12 advertencias; 15,83 s.** Se conservan los 488 casos anteriores. Los siete TXT permanecen sin cambios en esta fase.

La corrección distingue condiciones pendientes de evidencia recuperada: no se vuelve a pedir apellido cuando ya se confirmó; si el índice no aporta una regla, el diagnóstico señala corpus/índice y no pide reformular una consulta ya identificada.

## Fase B — Disposiciones generales de adultos

### Procedencia y alcance

Los tres TXT de adultos conservan el hash y la procedencia del PDF específico. Se añade en su cabecera la **confirmación explícita del usuario de 2026-10-27**, distinta de los PDF: plazo referencial común a todas las modalidades DNI y disposiciones solicitadas en esta tarea. Se revisaron los cuatro TXT originales para reutilizar formulaciones de advertencias, plazo, seguimiento y el enlace oficial `https://serviciosportal.reniec.gob.pe/cetdnipi/inicio.htm`.

No se crea un octavo documento ni se modifican los cuatro originales. No se traslada la afirmación del TXT antiguo de seguimiento de que el 100 % permite recoger automáticamente: las reglas nuevas exigen confirmar disponibilidad con el seguimiento y las indicaciones consulares, conforme a la instrucción explícita del usuario.

Cada TXT de adulto añade tres bloques íntegros:

- `[[REGLA:advertencias]]`: cita previa, vigencia de requisitos y fotografías cuando se exijan.
- `[[REGLA:plazo]]`: texto confirmado de aproximadamente 3 a 4 meses desde el trámite, referencial según RENIEC y envío; no implica disponibilidad para entrega.
- `[[REGLA:seguimiento]]`: consulta personal en RENIEC, verificación del avance del 100 %, sin solicitar el número dentro del asistente y sin garantía automática de disponibilidad.

Solo se sustituyen en la regla `general` las frases que decían que el PDF no especificaba plazo, por una referencia a la regla común registrada por separado. Se mantienen tasa, cantidades fotográficas y demás requisitos particulares. Las reglas específicas previas (`datos`, matrimonio, divorcio, viudez, etc.) son idénticas a la base. Las tres nuevas disposiciones comunes son iguales en los tres archivos.

### Selección y control de salida

- `adult_context.py`: los temas `plazo`, `seguimiento` y `advertencias` autorizan solo la regla común correspondiente del procedimiento. No se exige transición civil o país para esos temas si no son relevantes. Las contradicciones materiales y dudas de titular siguen bloqueando; las reglas comunes no las confirman.
- `classification.py`, `state.py`, `context_policy.py`: tema interno `advertencias`. Seguimiento de un procedimiento adulto activo usa su propia ficha y conserva la operación; seguimiento genérico o de los procedimientos anteriores conserva la ruta previa. No se amplía el catálogo de operaciones.
- `combination_guard.py`: renderiza de forma determinista las reglas comunes, incluso para un procedimiento individual. Si una derivación autorizada utiliza dos fichas, exige la regla común en ambas y coincidencia textual; no sintetiza diferencias. Si no coinciden, se abstiene. La protección del verificador sustituye también una afirmación libre de entrega garantizada al 100 %. Para respuestas fuera de estas reglas, el alcance de verificación sigue siendo el documentado anteriormente.
- La posibilidad de informar un plazo general en una solicitud de renovación con estado civil **no autoriza esa combinación**. Una repregunta de tasa o requisitos mantiene la restricción documental existente. El plazo común no determina el coste conjunto, el número de fotografías conjunto ni la acumulación de actas.
- No se añaden automáticamente advertencias al coste, fotografías o requisitos; cada tema recupera únicamente sus reglas autorizadas. Una regla general aislada no suple `datos`, `italiano`, matrimonio u otra regla específica que falte.
- `dni_graph.py`: conserva el diagnóstico de abstenciones y diferencia también disposiciones comunes inconsistentes de una respuesta factual disponible.

### Pruebas de Fase B y validación integral

Catorce casos nuevos en `test_adult_general_rules.py`: matriz de tres modalidades por tres temas generales; retorno a requisitos con aclaración pertinente; reglas específicas ausentes; combinación civil no autorizada; rechazo de garantía automática al 100 %; y coherencia de reglas comunes entre fichas.

Se mantienen todos los casos anteriores. Dos expectativas cambian por la nueva confirmación documental: la repregunta de plazo civil selecciona `plazo` en lugar de `general`, y el plazo de una derivación ya no tiene que abstenerse por ausencia de información. No se desactivan comprobaciones de tasas, cantidades ni fuentes.

Se ejecutó la suite completa después de la Fase A y nuevamente después de la Fase B con el mismo comando anterior. **Resultado final de Fase B: 517 aprobadas, 6 de integración excluidas, 12 advertencias; 13,51 s.** Las seis pruebas de integración externa siguen excluidas. No se ejecutaron OpenAI real, FAISS real ni validación nativa Windows; las pruebas de recuperación usan fragmentos reales del corpus y proveedores simulados.

### Verificaciones de integridad

- Siete TXT, sin octavo; cuatro originales idénticos respecto a `e19d9f8`.
- Regla específica de cada caso de adulto preservada byte a byte; en la regla `general`, los requisitos se conservan y solo se aclara la procedencia del plazo.
- Seguridad, autenticación, privacidad, cookies, concurrencia, retención, endpoints y dependencias sin cambios.
- No se modifica el algoritmo de similitud, el modelo de embeddings ni la segmentación. Sí se amplía el corpus y el selector de reglas autorizadas, y se reintenta recuperación de forma acotada cuando falta una regla.
- `git diff --check` sin errores.

## Despliegue Windows/Conda y reconstrucción FAISS

**Esta entrega sí requiere reconstruir el índice**, a diferencia de las correcciones previas: se añadieron nueve bloques documentales en los tres TXT de adultos. Un índice anterior no contiene `plazo`, `seguimiento` ni `advertencias`; el diagnóstico de reglas faltantes permite identificar esa situación sin inventar respuestas.

Con árbol limpio y el entorno existente Python 3.11:

```powershell
git fetch origin
git switch feature/dni-mayor-ampliacion
git pull --ff-only origin feature/dni-mayor-ampliacion
conda activate tfm-piloto
$env:GRADIO_ANALYTICS_ENABLED="False"
$env:PYTHONDONTWRITEBYTECODE="1"
python -B -m pytest -q --tb=short -p no:cacheprovider
```

Detener la aplicación; revisar los siete TXT y respaldar/versionar localmente el índice previo fuera de Git. Reconstruir con las credenciales locales existentes (no modificar `.env` ni publicarlas):

```powershell
python -c "from app.rag.index_builder import crear_indice_faiss; print(crear_indice_faiss())"
python -m app.ui
```

Ese comando usa embeddings reales: **se proporciona para ejecución posterior, no se ejecutó aquí**. No reutilizar un índice de otra versión del corpus al comparar ramas; Git no restaura índices ignorados.

Linux, con entorno virtual existente:

```bash
GRADIO_ANALYTICS_ENABLED=False PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m pytest -q --tb=short -p no:cacheprovider
.venv/bin/python -c 'from app.rag.index_builder import crear_indice_faiss; print(crear_indice_faiss())'
.venv/bin/python -m app.ui
```

### Validación real pendiente

En sesión nueva, repetir la conversación de viudez y «no, he mantenido siempre mi apellido materno», luego «no». Deben conservarse viudez, Italia, condición italiana y apellido no; para requisitos se necesitan `general`, `viudez_italia` e `italiano` de la ficha civil. Debe mantenerse la observación documental sobre actas, sin lista acumulada inferida.

Si faltan reglas, revisar el campo `verificacion` y el estado diagnóstico `reglas_faltantes`: no se debe volver a preguntar por un apellido ya confirmado. Una abstención debe indicar `abstencion_documental`, no `ok`. Revisar marcadores completos e índice correcto antes de modificar el lenguaje de la consulta.

En conversaciones independientes, probar menor primera inscripción/renovación, consulta de estado, amarillo/azul, renovación adulta, rectificación y matrimonio/divorcio/viudez. Para cada adulto, consultar plazo, seguimiento y advertencias; comprobar fuente y regla, ausencia de tasas o requisitos añadidos y límite de disponibilidad al 100 %. Volver a requisitos para comprobar que la información general no elimina aclaraciones o suple fuentes particulares.

## Riesgos residuales y criterio de cierre

La extracción es determinista y no cubre toda paráfrasis; las contradicciones se aclaran. Los reintentos mejoran recuperación, pero no garantizan que un top‑k incluya las reglas necesarias: la abstención sigue siendo obligatoria. Aumentan potencialmente latencia y consumo de embeddings; siguen siendo consultas externas con los límites existentes.

La confirmación del plazo común procede del usuario y del corpus previo, no de una nueva lectura web de las fichas adultas. Las ambigüedades normativas de actas y tasas conjuntas permanecen abiertas. Los indicadores distinguen abstención de salida disponible, pero no son certificación jurídica ni verificación factual universal.

No se considera terminada la validación por pasar pytest. Queda pendiente la validación real descrita, en Windows/Gradio con el índice reconstruido, OpenAI y FAISS reales. Los commits se publican únicamente en la rama del PR #4, sin fusión ni cambio de su estado de revisión.
