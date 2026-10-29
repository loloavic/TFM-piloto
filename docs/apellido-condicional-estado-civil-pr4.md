# Divorcio y viudez: apellido como condición adicional — PR #4

Fecha: 29/10/2026. Base: 4b1dc9c. Rama: feature/dni-mayor-ampliacion. No se modifica main, no se fusiona el PR ni se cambia su estado.

## Causa confirmada y nueva política

`adult_context.actualizar()` añadía apellido a los datos obligatorios de divorcio y viudez. Aunque el procedimiento y los documentos principales fueran inequívocos, el contexto mantenía un pendiente material y bloqueaba toda recuperación. El plan solo autorizaba la regla apellido después de un sí.

La regla vigente ya es condicional: «Si desea recuperar el apellido materno tras divorcio o viudez: acta de nacimiento original. Si se emitió en Perú, aplicar las condiciones generales de documentos peruanos». No hay necesidad documental de modificar los TXT para explicar esa posibilidad sin preguntar antes.

| Estado de la condición | Orientación |
|---|---|
| Desconocida | Requisitos principales y apartado separado **Recuperación del apellido materno (solo si la necesita)**, con el texto condicional autorizado. El estado sigue desconocido |
| Afirmación expresa | Se incluye la documentación adicional para la recuperación solicitada |
| Negativa expresa | Se excluye la regla apellido y el acta de nacimiento de la respuesta |
| Contradicción expresa | Se mantiene una aclaración material antes de recuperar documentos |
| Sí/no sin pregunta pendiente | No se infiere una decisión sobre el apellido |

Solo se muestran formalidades respaldadas: para el acta de nacimiento emitida en Perú, las condiciones generales autorizadas. No se inventan apostillas, legalizaciones ni certificaciones para otros lugares de emisión. No se afirma que la persona utiliza un apellido de casada ni se solicitan sus apellidos reales; se explica la recuperación únicamente como condición adicional, no como obligación universal.

## Implementación por archivo

- `app/graph/adult_context.py` / actualizar: elimina apellido desconocido de las aclaraciones obligatorias; conserva contradicciones. Las respuestas explícitas se procesan también cuando la condición es opcional y desconocida, incluso en la primera consulta civil completa. No necesita una pregunta previa para entender «no, ya utilizo mi apellido materno».
- `app/graph/adult_context.py` / plan: en requisitos/otra de divorcio o viudez autoriza apellido si la decisión es desconocida o afirmativa; una negativa lo excluye. Coste/cita y reglas comunes no incorporan esa regla.
- `app/graph/presentation.py`: factoriza condiciones generales y detalles fotográficos, separa documentación principal y apartado de apellido. Conserva íntegros los textos y condiciones autorizados; la regla de apellido mantiene su formulación condicional. No añade requisitos desde información libre del ciudadano.
- `app/graph/combination_guard.py`: amplía el formato determinista de requisitos a divorcio y viudez peruana, además de las ramas italianas ya controladas. Exige el plan completo, verifica fuentes y duplicados y recompone exactamente la misma salida en el verificador. No se realiza una reformulación libre LLM posterior.
- `tests/test_optional_surname.py`: 31 regresiones nuevas.
- Cuatro archivos de pruebas previas (`test_adult_dni`, `test_operation_goal_change`, `test_widow_answers`, `test_widow_stabilization`): mantienen todos los casos, adaptando los pendientes obligatorios y expectativas de generación/recuperación que cambian intencionadamente. Se comprueban documentos en la respuesta controlada en vez de exigir una llamada LLM. Las respuestas binarias legítimas siguen probadas sobre una contradicción pendiente; un no aislado sin pregunta no pasa a significar automáticamente no recuperar apellido. Se ajustan mocks para la recuperación que ahora sucede en el primer turno.
- README, guía principal y este informe: política actual y validación reproducible.

No cambian clasificación de operaciones, titular, vigencia, tarifas, no acumulación, RuleIntegrity, API, sesiones, privacidad o seguridad. Se conservan la combinación de renovación y rectificación de datos y las restricciones para renovación con estado civil. No se generaliza la sustitución italiana de documentos de defunción.

## Ejemplos

**Divorcio, sin decisión sobre apellido**

Antes: «¿Desea recuperar el apellido materno?», sin documentación principal.

Ahora: documentación matrimonial principal, con acta peruana original y anotación de disolución del divorcio, condiciones generales aplicables y apartado aparte «Recuperación del apellido materno (solo si la necesita)». El acta de nacimiento no aparece en la lista principal; se conserva «Si desea recuperar…» y la condición de emisión en Perú.

**Cónyuge italiano fallecido en Italia, sin decisión sobre apellido**

Antes: aclaración obligatoria sobre apellido.

Ahora: defunción y matrimonio se presentan por separado. Se mantiene acta plurilingüe municipal legalizada por Prefectura y sustitución de la certificación consular de defunción para ese supuesto; matrimonio registrado en Perú y matrimonio registrado en oficina consular conservan alternativas distintas. Después se indica la posibilidad de recuperación del apellido sin exigirla a todo ciudadano.

**Renovación a 61 días → divorcio independiente**

El cambio de objetivo sigue funcionando y ahora responde directamente con fuentes civiles y la condición opcional, sin un turno obligatorio de apellido. Solicitudes adicionales de estado civil sobre una renovación a 59 días continúan sujetas a las restricciones de combinación, no a la política de no acumulación de datos.

## Integridad documental y límites

Apellido es opcional como decisión del ciudadano; la fuente sigue siendo obligatoria si se pretende comunicar su contenido. Si una regla incluida en el plan está ausente, obsoleta, incompleta o contradictoria, se conserva la abstención documental. No se inventa el apartado ni se responde desde TXT ausentes del índice. Una negativa permite responder sin esa regla porque ya no forma parte del plan autorizado.

Las aclaraciones de país de defunción y nacionalidad relevante permanecen cuando son necesarias. La viudez de otros supuestos conserva sus reservas y no hereda el caso italiano. Una contradicción de apellido sí pide aclaración; una ausencia de decisión no.

Los textos técnicos originales permanecen en contexto/fragmentos y documentos internos. La salida ciudadana utiliza los formatos existentes, incluida la presentación desplegable de características fotográficas completas. No cambia el contrato de respuesta.

## Pruebas ejecutadas

Antes de modificar producción se ejecutaron las dos consultas de referencia nuevas: **2 pruebas fallidas**, porque ambas devolvían general y pedían aclaración de apellido.

Suite final: **839 aprobadas, 6 de integración excluidas, 12 advertencias de dependencias, 12,06 s**, Python 3.11/Linux. Se mantienen los 808 casos anteriores y se añaden 31. No se eliminan pruebas ni se introducen exclusiones nuevas.

Cobertura nueva: divorcio, viudez italiana y peruana con decisión desconocida/sí/no; respuestas explícitas posteriores; no atribución de sí/no espontáneo; contradicción y resolución; condiciones peruanas; separación visual y factual de documentos principales/opcionales; fuentes ausentes/obsoletas/contradictorias para regla principal y apellido; exclusión de regla negada; verificador con acta de nacimiento universal y tasa inventada; defunción material pendiente; repreguntas de actas, coste/cita, cambio de titular y sesión independiente. Las regresiones anteriores conservan fuentes incompletas, renovación y combinaciones, concurrencia, seguridad, privacidad y borrado.

No se utilizó OpenAI real ni se reconstruyó/modificó FAISS de aplicación. Las pruebas de generación utilizan proveedores simulados; la suite existente incluye FAISS temporal con vectores artificiales. No hay dependencias nuevas ni cambios de credenciales.

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

No reconstruir FAISS por esta entrega: siguen intactos siete TXT y 44 fragmentos. Usar el índice ya sincronizado; `python -m app.rag.inspect_rules` sin --consulta permite comprobación sin OpenAI. Reiniciar la aplicación y abrir conversaciones nuevas.

Validar las consultas de referencia de divorcio y viudez italiana, sin declarar apellido: deben informar en el primer turno sin pregunta obligatoria. Después expresar negativa y comprobar ausencia de acta de nacimiento; expresar afirmación y verificar su apartado y condiciones. Repetir viudez peruana, país de defunción desconocido, contradicción, 61 días → divorcio independiente, 59 días → solicitud civil adicional, coste/cita y cambio de titular. Usar datos ficticios; no proporcionar apellidos reales.

Quedan pendientes la conversación con proveedor real y revisión visual en Windows/Gradio. Los formatos deterministas de requisitos tienen comparación final; otros temas individuales conservan sus controles anteriores y `ok` no certifica exactitud factual universal. El vocabulario de respuestas explícitas sigue siendo acotado. No se completa ningún supuesto administrativo no documentado ni se afirma vigencia normativa externa.
