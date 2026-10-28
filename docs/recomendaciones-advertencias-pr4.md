# PR #4: recomendaciones generales como tema de advertencias

> Evidencia histórica de su entrega. El estado consolidado, pruebas y correcciones posteriores se describen en [integridad y métricas del PR #4](integridad-metricas-pr4.md). Los resultados de este informe corresponden a su versión.


27 de octubre de 2026. Base `a57a909`, rama `feature/dni-mayor-ampliacion`.

## Causa confirmada y reproducción

La función existente se llama `tipo_consulta()` en `classification.py` (no `tema_consulta()`). El patrón de advertencias reconocía advertencias, precauciones y verificar antes de la cita, pero no recomendaciones ni revisar/tener en cuenta antes de acudir.

La consulta reportada quedaba en `otra`. La transición conservaba correctamente operación y circunstancias de viudez. El plan de `adult_context.py`, al recibir `otra`, autorizaba las reglas particulares de la ficha civil. No era un fallo de ranking ni de recuperación exacta: nunca se solicitaba `advertencias`.

Antes de modificar producción se ejecutaron seis casos multivuelta: **cinco fallaron y uno pasó**. Precauciones ya estaba reconocido; las cinco expresiones restantes reproducían la ausencia del tema general. La prueba comprueba los hechos canónicos y no exige que cambie su esquema ni la lógica de autorización.

## Corrección mínima

- `app/graph/classification.py`, únicamente `tipo_consulta()`: añade recomendaciones en singular/plural y las construcciones tener en cuenta/revisar/verificar antes de acudir/ir/cita. Enmascara solicitudes negadas de recomendaciones antes de identificar el tema. Si la frase nombra un objeto específico (coste, fotografías, requisitos/documentos o reserva/lugar/horario de cita), ese objeto tiene prioridad sobre la fórmula genérica de recomendación. «Para mi cita» no es por sí solo una solicitud de reserva. Se conserva la prioridad anterior de seguimiento y plazo.
- `tests/test_general_advice.py`: 22 casos nuevos: seis conversaciones equivalentes, catorce controles de prioridad/negación/ambigüedad, regla ausente y retorno a requisitos con sesión independiente.
- Este informe documenta la evidencia, ejecución y límites.

No se modifica `context_policy.py`, `adult_context.py`, el guard determinista ni el recuperador. Cambia el tema a `advertencias`; permanecen titular adulto, operación rectificación, transición, país de defunción, nacionalidad y decisión sobre apellido. El plan existente autoriza entonces exclusivamente `dni_mayor_estado_civil.txt#advertencias` y el control existente genera su texto sin LLM.

## Resultado esperado y comprobado

Para la pregunta reportada se devuelve la regla general de advertencias: no acudir sin cita previa, comprobar que los requisitos estén vigentes y, cuando se exijan fotografías, verificar sus características. No se recuperan ni repiten `viudez_italia` o `italiano` para esa repregunta.

Si la regla falta tanto en recuperación semántica como exacta, se conserva la abstención y se diagnostica `dni_mayor_estado_civil.txt#advertencias`. No se usan requisitos particulares como sustituto. Al volver a preguntar qué documentos presentar, se seleccionan de nuevo las reglas particulares correctas; otra conversación no hereda el contexto.

Las consultas sobre coste, fotos, documentos o reserva mantienen esos temas aunque contengan la palabra recomendaciones. Las negaciones no activan advertencias. Frases sin objeto o contexto suficiente, como «¿Qué debo tener en cuenta?», permanecen en `otra`; no se amplía aquí la política conversacional de consultas ambiguas.

## Pruebas ejecutadas

Linux/Python 3.11.17, entorno existente:

```bash
GRADIO_ANALYTICS_ENABLED=False XDG_CACHE_HOME=/tmp/tfm-cache PYTHONDONTWRITEBYTECODE=1 env -u OPENAI_API_KEY -u TFM_OPENAI_API_KEY .venv/bin/python -B -m pytest -q --tb=short -p no:cacheprovider
```

**560 aprobadas, 6 de integración excluidas, 12 advertencias de dependencias; 9,10 s.** Se conservan los 538 casos anteriores sin editar sus expectativas. Se ejecutan también seguridad, privacidad, sesiones, concurrencia, separación documental y recuperación exacta.

No se utilizó OpenAI real ni se reconstruyó el índice de la aplicación. La suite incluye las pruebas locales previas de FAISS con índices temporales y vectores artificiales; no acredita el comportamiento semántico de OpenAI ni validación nativa de Windows. Los siete TXT y la implementación de indexación permanecen iguales.

## Windows/Conda

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

No reconstruir FAISS por esta corrección: reutilizar el índice actualizado de siete documentos y 43 fragmentos. En una conversación nueva, resolver viudez/Italia/nacionalidad/apellido y preguntar la frase reportada. Debe conservarse `dni_adulto_rectificacion`, seleccionarse solo la regla `advertencias` de la ficha civil y aparecer las tres advertencias generales. Repetir con las cinco variantes, volver a documentos, preguntar coste/fotos/cita y comprobar que cada tema selecciona sus fuentes propias.

La validación real en Windows/Gradio con OpenAI queda pendiente de ejecución local. El reconocedor sigue siendo determinista y no cubre cualquier paráfrasis; las consultas con varios temas usan una prioridad explícita, no se introduce un planificador multitarea. No se altera seguridad, privacidad ni autorización documental. Main permanece intacta y el PR #4 no se fusiona.
