# P2.6 y política de confirmación conversacional

Base de revisión: `51b14f0`, rama `fix/dni-classification-context`, PR #2. La corrección no cambia la arquitectura, los controles de Fase 1A, el corpus, FAISS, credenciales ni dependencias.

## Diagnóstico y evidencia previa

La operación solo reconocía algunas formas adyacentes como «DNI vencido». No detectaba «Su DNI está vencido», «se venció» o «ya caducó» en contexto. Por ello heredaba primera inscripción incluso después de recibir evidencia incompatible de tenencia de un DNI.

El problema acumulado excedía el vocabulario: clasificación, herencia y confirmación se realizaban juntas, y una hipótesis podía convertirse en trámite activo antes de contrastarla con el contexto. Las correcciones locales de roles y negaciones no ofrecían una política de confirmación común.

Se ejecutaron ocho regresiones nuevas **antes de modificar el código sobre `51b14f0`: ocho fallos**. Incluían seis variantes de caducidad y dos secuencias completas con confirmación posterior. El flujo original recuperaba documentación de primera inscripción donde debía detenerse.

## Diseño aplicado

Se conserva el clasificador determinista. Se separan estas responsabilidades:

1. `normalizar`: normalización lingüística existente.
2. `identificar_roles` y `solicitante`: apoyo, acompañamiento, titular, categoría de edad y ambigüedad documental. El texto que describe un documento de apoyo no demuestra tenencia del DNI del titular.
3. `dni_vencido` y `operacion`: evidencia de caducidad asociada al DNI, operaciones afirmativas y negaciones específicas. Las referencias sin sujeto requieren contexto previo; no se infiere renovación de un «está vencido» aislado sin contexto DNI.
4. `_clasificar_candidato`: propuesta interna a partir de las reglas previas, sin capacidad de confirmar por sí sola.
5. `clasificar`: contraste con el trámite confirmado, resolución o conservación de dudas y actualización final.
6. `pregunta_contextual`: recuperación del tema pendiente al aclararse, para búsqueda y entrada al redactor.

### Estado sin nuevos datos personales

| Campo | Semántica |
| --- | --- |
| `tramite_actual` | Último trámite confirmado. Durante una duda conserva el anterior; queda vacío si todavía no se confirmó ninguno. Su existencia **no habilita recuperación** mientras se requiere aclaración. |
| `operacion_dni`, `contexto_solicitante` | Operación conocida o incompleta y categorías mínimas existentes. Una operación explícitamente rechazada se borra de `operacion_dni`; el último trámite confirmado puede permanecer como referencia histórica bloqueada. |
| `requiere_aclaracion`, `motivo_aclaracion` | Única decisión de bloqueo y motivo concreto. Se reutilizan, sin añadir otro booleano de confirmación. |
| `decision.tramite_candidato` | Hipótesis provisional, incluso cuando contradice al confirmado. No se usa directamente para recuperar requisitos. |
| `decision.evidencias` | Códigos como `tenencia_dni`, `operacion:renovacion`, `negacion:primera_vez`, `titular_explicito`, `contexto_confirmado`. No se almacenan fragmentos personales. |
| `decision.faltantes` | Códigos de información necesaria, por ejemplo edad u operación. |
| `decision.contradicciones` | Motivos que requieren confirmación, incluidos operación, titular, edad o documento ambiguo. Se conservan mientras la duda siga abierta. |
| `decision.consulta_pendiente` | Tema de la consulta que debe retomarse: coste, plazo, cita, requisitos, seguimiento u otra. No se copia la pregunta original. |

La formulación original sigue en el historial existente, limitado a seis turnos. Si sale del historial, se conserva el tema pendiente y los metadatos mínimos, no todos sus matices. `pregunta_contextual` añade una pregunta canónica del tema a la entrada del redactor y la búsqueda una vez aclarada. El texto del turno almacenado se restaura antes del verificador/historial. No se guardan nuevas edades exactas, identidades, números de DNI ni copias de mensajes.

La decisión se almacena en los mismos checkpoints efímeros y queda sujeta al TTL, autorización y borrado existentes. No se añade otro almacén ni se cambia la concurrencia.

## Política de confirmación

- Una solicitud clara desde el inicio, como «Quiero renovar el DNI vencido de mi hijo de 10 años», selecciona renovación sin aclaración adicional.
- Un hecho nuevo incompatible con el trámite confirmado, como primera inscripción seguida de «Su DNI está vencido», conserva el confirmado y propone renovación como candidato. Pregunta únicamente si ya tenía DNI o si es su primer DNI.
- «¿Cuánto cuesta?» no resuelve esa disyuntiva. Mantiene la aclaración y registra coste como consulta pendiente. «Sí» sin precisar una de las opciones tampoco confirma ninguna.
- «Sí, ya tenía DNI» resuelve hacia renovación. «Nunca tuvo DNI» como respuesta a esa aclaración confirma primera inscripción. Se retoma el tema pendiente sin volver a preguntar la operación.
- «Me equivoqué, ya tenía DNI», una negación explícita del procedimiento anterior seguida de la alternativa, o una nueva solicitud inequívoca permiten rectificación directa.
- Una contradicción inversa —renovación y luego el hecho «Nunca tuvo DNI»— también pide confirmación si no es una rectificación explícita.
- Varios titulares materiales, finalidad documental ambigua o categorías de edad incompatibles provocan una pregunta dirigida al dato incierto. No se solicitan simultáneamente todos los datos ya conocidos.
- Un cambio explícito de procedimiento/tema deja atrás el pedido pendiente. «Olvida lo anterior» abandona el contexto de clasificación y solicita un nuevo objetivo; no equivale a borrar el historial, para lo cual sigue existiendo el mecanismo autorizado de eliminación.
- Un procedimiento identificado pero no documentado mantiene la abstención existente. No se añaden requisitos de adultos ni nuevos procedimientos.

### Puertas documentales

`recuperar_documentos` comprueba `requiere_aclaracion` además de la intención. Devuelve fuentes y contexto vacíos sin invocar el recuperador cuando hay una duda pendiente, incluso si quedara una intención residual específica. El envoltorio del redactor fuerza la aclaración determinista en ese caso. Por tanto, conservar el trámite confirmado no permite generar requisitos de ese trámite mientras la contradicción permanezca abierta.

El literal del prompt funcional de generación no se modifica. Solo se adapta su entrada para incluir el tema ya aclarado. El verificador factual, la construcción del grafo y la función de historial son idénticos a la base en comparación AST. La reducción de datos antes/después del proveedor sigue pasando por las funciones de privacidad existentes.

## Antes y después

| Secuencia | Base | Corrección |
| --- | --- | --- |
| Primer DNI → DNI vencido → coste | Continúa primera inscripción | Aclaración; ninguna recuperación/LLM documental |
| Anterior → «ya tenía DNI» | Sin confirmación explícita del conflicto | Confirma renovación y responde al tema coste con su fuente |
| Anterior → «nunca tuvo DNI» | Conserva primera por inercia | Confirma primera y recupera su fuente para la consulta pendiente |
| Coste de renovación sin edad → hijo de 10 años | Ya corregido en P2.2 | Se conserva; tema coste explícito en la entrada contextual |
| Acompañante adulto / DNI de apoyo vencido | Riesgo de contaminar titular/operación | No se usa el estado del documento de apoyo como operación del titular |
| Pregunta pendiente fuera de seis turnos | Solo quedaba la información retenida incidentalmente | Se conserva el tema mediante código, sin ampliar el historial |

## Matriz acumulativa y ejecución

Se conservan los 179 casos deterministas anteriores y se añaden **46 casos**. Las pruebas unitarias contrastan intención, candidato, confirmado y motivos. Las pruebas del grafo contrastan también fuentes, llamadas al recuperador/proveedor simulado, respuesta de aclaración/abstención y continuidad de sesión.

| Cobertura | Evidencia comprobada | Resultado |
| --- | --- | --- |
| Adulto/menor, primera/renovación | Categorías, corpus disponible y abstención adulta | Aprobado |
| Edad o destinatario incompleto | Operación conservada y consulta original contextualizada | Aprobado |
| Titular, acompañante y apoyo | P2.1–P2.4 y documento de apoyo vencido | Aprobado |
| Negaciones | Duplicado, primera inscripción, caducidad negada y rechazo de renovación | Aprobado |
| Caducidad | Vencido/caducado/expirado, referencias con sujeto y elipsis contextual | Aprobado |
| Contradicciones y rectificaciones | Ambas direcciones, mismo turno, confirmaciones alternativas y «sí» ambiguo | Aprobado |
| Varios titulares | Pregunta dirigida, sin recuperación ni generación documental | Aprobado |
| Consultas pendientes | Coste, plazo, requisitos, cita y seguimiento; historial agotado; sin bucle tras aclarar | Aprobado |
| Abandono y cambios explícitos | Pasaporte, adulto, renovación y cancelación de contexto | Aprobado |
| Sesiones | Aislamiento y reinicio previos; decisión pendiente eliminada por TTL y borrado | Aprobado |
| Seguridad | Suite previa de autorización, HTTP Gradio, privacidad, métricas y concurrencia | Aprobado |

Comando ejecutado, sin claves reales ni servicios externos:

```bash
GRADIO_ANALYTICS_ENABLED=False XDG_CACHE_HOME=/tmp/tfm-cache PYTHONDONTWRITEBYTECODE=1 \
  env -u OPENAI_API_KEY -u TFM_OPENAI_API_KEY \
  .venv/bin/python -B -m pytest -q --tb=short -p no:cacheprovider
```

**225 aprobados, 6 de integración excluidos, 12 advertencias de dependencias; 6,34 s; Linux/Python 3.11.17.** Los tests de proveedor y recuperación usan simulación; no certifican respuestas de OpenAI real ni recuperación semántica FAISS real. Las advertencias corresponden a dependencias existentes. `git diff --check` correcto.

## Windows/Conda y despliegue

No se necesitan dependencias, variables ni migraciones nuevas. Mantener Python 3.11 y los mismos mecanismos de arranque seguro. Al actualizar debe reiniciarse el proceso; los checkpoints son en memoria y se pierde la conversación anterior como ya ocurría. No se ofrece migración de sesiones activas entre versiones del esquema.

Desde la raíz, en PowerShell y con las dependencias existentes:

```powershell
conda activate tfm-piloto
$env:GRADIO_ANALYTICS_ENABLED = "False"
$env:PYTHONDONTWRITEBYTECODE = "1"
python -B -m pytest -q --tb=short -p no:cacheprovider
```

La configuración de pytest excluye integración por defecto; esta suite no requiere claves OpenAI. Para la validación funcional local con las credenciales ya administradas por el usuario, arrancar según la [guía de seguridad](seguridad-fase-1.md). Repetir en conversaciones nuevas la secuencia P2.6 y cada confirmación alternativa, coste sin edad con aclaración, acompañantes y cambio explícito de tema. No usar datos personales reales en esas comprobaciones. No se ha ejecutado aquí Windows/Conda nativo, navegador JavaScript completo ni integración real con OpenAI.

## Riesgos residuales y dictamen

La solución ofrece una política verificable sobre señales deterministas, no comprensión exhaustiva del español. Siguen existiendo paráfrasis desconocidas, referencias a varios documentos difíciles de resolver y pérdida de matices del pedido original cuando sale del historial limitado. Las marcas de rectificación se reconocen por patrones: no constituyen una garantía general de corrección de referentes. La política puede solicitar aclaraciones conservadoras.

El último trámite confirmado retenido durante una duda es una referencia histórica bloqueada, no un permiso para recuperar sus requisitos. El tipo de consulta sigue siendo único; si el ciudadano cambia a otro tema mientras espera, se conserva ese tema más reciente, no una cola de varias consultas. Las limitaciones de calidad documental y del verificador factual permanecen pendientes de Fase 1B.3. No se atribuye capacidad legal a acompañantes/representantes ni se valida normativamente el corpus.

**Preparado para revisión técnica y posterior validación local en Windows.** El éxito determinista no garantiza ausencia de defectos, precisión lingüística general ni corrección factual de un modelo real. El PR #2 debe revisarse y permanecer sin fusionar.
