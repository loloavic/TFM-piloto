# PR #4: actualización de estado civil y continuidad

> Evidencia histórica de su entrega. El estado consolidado, pruebas y correcciones posteriores se describen en [integridad y métricas del PR #4](integridad-metricas-pr4.md). Los resultados de este informe corresponden a su versión.


27 de octubre de 2026. Base `e4e31e1`, rama `feature/dni-mayor-ampliacion`.

## Causa raíz confirmada

La consulta inicial ya expresaba titular propio y mayoría de edad. `solicitante()` reconocía esa información al principio, pero el filtro de `presentar` descartaba el titular cuando no encontraba un objeto propio de trámite entre los patrones autorizados. La protección previa incluía rectificar/corregir datos propios, pero no actualizar/cambiar **mi estado civil**. Por ello, «¿Qué documentos debo presentar?» borraba la evidencia de titular y edad antes de emitir `EvidenciaTurno`.

`extraer_evidencia()` sí reconocía la modificación, la transición soltera/casada y el matrimonio en Perú. Sin edad adulta confirmada, la política canónica no podía asociar esa petición a rectificación adulta; solicitaba la operación. En el segundo turno, `renuevo` ya era reconocido como renovación, pero la edad seguía vacía desde el primer turno. No se trataba de otra pérdida producida al aclarar la operación ni de un problema del recuperador.

Se escribieron tres reproducciones antes de modificar producción (consulta inicial y secuencia con dos variantes de aclaración); **las tres fallaron**. La corrección hace pasar los mismos casos sin alterar la política canónica.

## Corrección mínima

- `app/graph/classification.py`, `solicitante()`: reconoce la solicitud explícita sobre **mi estado civil** mediante actualizar/cambiar/rectificar/corregir, con referencia a DNI, antes del filtro de presentación documental. La máscara de solicitudes negadas incluye actualizar y cambiar para no convertir una negación en titular afirmativo.
- `tests/test_civil_continuity.py`: trece casos nuevos de reproducción y regresión.
- Este informe: causas, alcance, pruebas e instrucciones locales.

No se modifican los extractores de condiciones civiles, operaciones reconocidas, transiciones, validación de contexto, autorización documental ni el control determinista de combinaciones. La corrección preserva la evidencia para que esos mecanismos existentes operen correctamente. No se requieren nuevas categorías persistentes, dependencias ni modelos.

## Comportamiento después de corregir

| Intervención | Resultado comprobado |
|---|---|
| Consulta reportada inicial | Titular propio adulto; operación rectificación; modificación estado civil; transición `matrimonio`; lugar `peru`. Intención `dni_adulto_rectificacion`; solo ficha civil |
| Repregunta de requisitos | Reglas `general` y `matrimonio_peru`, sin documentos de renovación ni de menores |
| «seria un renuevo» / «Sería una renovación» | Mantiene titular adulto y condiciones previas; operación renovación. Combinación sin respaldo: explicación restrictiva, sin fuentes, sin recuperador ni LLM adicionales |
| Matrimonio en Italia | Categoría `extranjero`; solo regla de matrimonio extranjero y general |
| Divorcio y recuperación de apellido | Categorías divorcio/apellido sí; reglas correspondientes |
| Viudez con fallecimiento en Italia | Mantiene lugar, nacionalidad categórica y decisión sobre apellido; conserva observación documental de actas, sin resolverla por inferencia |
| Cambio a hijo menor | Elimina condiciones del titular anterior y utiliza solo renovación de menor |
| Renovación adulta ordinaria después de cambio de titular | Sin circunstancias civiles heredadas; solo ficha de renovación adulta |
| «No quiero renovar» durante cambio civil | Rechaza renovación y conserva rectificación civil |
| Requisitos, tasa y cita en varios turnos | Mantiene condiciones categóricas y selecciona las reglas del tema correspondiente |
| Falta únicamente lugar del matrimonio | Pregunta `adulto_matrimonio`, sin volver a preguntar edad u operación |
| Otra sesión | No hereda circunstancias ni edad de la anterior |

La transición se almacena como categoría `matrimonio`, no como texto personal o género. Lugar es `peru`/`extranjero`; apellido solo sí/no. Las pruebas comprueban el esquema de esos datos (valor, estado, turno, revisión, origen), sin nombres o apellidos reales. El historial y su minimización parcial permanecen como estaban; no se afirma anonimización completa del texto libre.

## Resultado ejecutado

Linux, Python 3.11.17; entorno virtual existente:

```bash
GRADIO_ANALYTICS_ENABLED=False XDG_CACHE_HOME=/tmp/tfm-cache PYTHONDONTWRITEBYTECODE=1 env -u OPENAI_API_KEY -u TFM_OPENAI_API_KEY .venv/bin/python -B -m pytest -q --tb=short -p no:cacheprovider
```

**450 aprobadas, 6 de integración excluidas, 12 advertencias de dependencias; 11,25 segundos.** Son los 437 casos anteriores, sin modificar sus expectativas, más trece nuevos. Incluye seguridad, privacidad, concurrencia, sesiones, negaciones, documentos de apoyo, amarillo/azul y control determinista de afirmaciones combinadas.

Los siete TXT y todo el código de RAG/FAISS, seguridad y sesiones permanecen iguales a la base. No se ejecutó OpenAI real, búsqueda semántica real, reconstrucción del índice ni validación nativa en Windows. No se modifica main ni se fusiona el PR.

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

No reconstruir FAISS por esta corrección: usar el índice de siete documentos ya validado localmente. En una sesión nueva, repetir los dos turnos reportados y comprobar la distinción entre ficha civil documentada y combinación con renovación no autorizada. En otra conversación, repetir requisitos, coste y cita sin aclarar renovación; deben seguir referidos a estado civil. Validar también el cambio a hijo menor y una sesión independiente.

## Límites

El reconocimiento sigue siendo determinista y no garantiza interpretar cualquier paráfrasis. No basta mencionar que el hablante es adulto para asignarle el DNI presentado como apoyo: las regresiones mantienen ese filtro. No se inventa un contrato combinado para renovación/estado civil; si se solicita, se comunica la limitación documental en lugar de preguntar por datos que ya se conocen. `verificacion: ok` de una explicación de alcance no certifica que exista una combinación consular autorizada.
