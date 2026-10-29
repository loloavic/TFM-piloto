# Renovación con pronombres — PR #4

Fecha: 29/10/2026. Base: fc53644. Rama: feature/dni-mayor-ampliacion. No se modifica main ni se fusiona el PR.

## Causa confirmada y reproducción

Los tres casos «Soy mayor de edad y mi DNI vence dentro de 59/60/61 días. ¿Puedo renovarlo ahora?» devolvían general porque `operacion()` reconocía renovar como palabra completa, pero no renovarlo. El detector posterior `explicit_renewal` repetía el patrón incompleto y la bandera solicitud tampoco reconocía la pregunta «puedo renovarlo». Además, `extraer_vigencia()` admitía «vence en», pero no «vence dentro de»: corregir solo el pronombre habría dejado desconocido el intervalo de 61 días y no habría aplicado su restricción.

Antes de modificar producción se ejecutaron las primeras 18 pruebas nuevas: **18 fallaron**. Tres reproducen el caso Gradio completo; otras quince combinan cinco formulaciones con 59/60/61 días. La variante «puedo renovar mi DNI» ya identificaba la operación, pero fallaba al conservar la vigencia expresada como «dentro de».

## Corrección mínima

| Archivo | Cambio |
|---|---|
| `app/graph/classification.py` | Patrón afirmativo de renovación con pronombres; negación alineada; detector posterior reutiliza `operacion(..., inferir_tenencia=False)` en vez de otro patrón incompleto. La bandera solicitud reutiliza la operación afirmativa ya validada, sin convertir el vencimiento en autorización |
| `app/graph/adult_context.py` | Añade «vence/vencerá dentro de» como forma equivalente a «vence/vencerá en» en el extractor existente; conserva categorías y umbral inclusivo sin cambiar política |
| `tests/test_renewal_pronouns.py` | 36 regresiones nuevas; no se modifica ninguna prueba anterior |
| README y este informe | Evidencia e instrucciones de validación local |

No se altera el plan documental, RuleIntegrity, plantillas, tasas ni no acumulación. Tampoco los TXT, FAISS, API, prompts, seguridad, sesiones, privacidad o dependencias. No requiere reconstruir FAISS.

La resolución del pronombre sigue sujeta al ámbito DNI establecido por el mensaje o la conversación canónica. Una consulta nueva «quiero renovarlo» sin referente no abre fuentes adultas; la mención de pasaporte no se convierte en DNI. Se mantienen negaciones antes de detectar afirmaciones y el rechazo persiste ante una mera observación de vencimiento. Una nueva solicitud afirmativa explícita sí puede rehabilitar la operación.

## Resultado esperado

| Expresión y vigencia | Clasificación / respuesta |
|---|---|
| «Puedo renovarlo ahora», 59 días | dni_adulto_renovacion; renovación procedente |
| «Puedo renovarlo ahora», 60 días | dni_adulto_renovacion; renovación procedente |
| «Puedo renovarlo ahora», 61 días | dni_adulto_renovacion; explica que no corresponde renovar todavía |
| «No quiero / no necesito / no corresponde renovarlo» | Renovación rechazada; sin fuentes que autoricen esa operación |

Los casos positivos recuperan únicamente `dni_mayor_renovacion.txt#general`; no seleccionan la política de combinación ni inventan documentos o tasas. La respuesta procede de la plantilla determinista existente y no llama al proveedor LLM.

## Pruebas ejecutadas

Suite completa: **717 aprobadas, 6 de integración excluidas, 12 advertencias de dependencias, 10,78 s**. Python 3.11/Linux, sin OpenAI real ni cambio del índice de aplicación.

Se conservan las 681 pruebas previas sin cambiar sus expectativas y se añaden 36 casos: originales 59/60/61, quiero/necesito/puedo renovar/me corresponde, negaciones en cada umbral y con DNI vencido, repreguntas de coste, rechazo persistente, rehabilitación explícita, aclaración con pronombre, reevaluación con mención de DNI amarillo, referente desconocido/pasaporte, cambio a titular menor y aislamiento de sesión nueva. Las pruebas existentes siguen cubriendo integridad, concurrencia, privacidad, autorización y no acumulación.

La intención adulta de renovación identifica la consulta incluso cuando no procede todavía; no equivale a declarar elegibilidad. `ok` conserva el significado limitado de los controles disponibles, no certificación factual universal.

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

Usar el índice ya sincronizado de siete TXT/44 fragmentos de la entrega tarifaria. No reconstruirlo por esta corrección de reconocimiento. Si se necesita comprobar su estado, `python -m app.rag.inspect_rules` sin --consulta no consume embeddings.

En Gradio abrir una conversación nueva para cada uno de los tres casos originales. Verificar intención adulta, fuente general exclusiva y resultado según 59/60/61. Después probar «no quiero renovarlo», una observación de vencimiento y «ahora sí, quiero renovarlo»; comprobar bloqueo y recuperación solo tras la afirmación explícita. Repetir una repregunta de coste y cambio a titular menor, con datos ficticios.

No se realizó validación nativa en Windows ni conversación con OpenAI/FAISS de producción. Subsisten los límites lingüísticos previos: el cambio no pretende resolver todos los pronombres o referentes ambiguos. No se añaden procedimientos ni se modifica ninguna autorización documental.
