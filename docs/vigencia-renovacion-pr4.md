# Vigencia y fidelidad de renovación adulta — PR #4

Fecha: 29/10/2026. Base: facfe3c. Rama: feature/dni-mayor-ampliacion. No se modifica main, no se fusiona el PR ni se cambia su estado.

## Procedencia y alcance

El usuario responsable del conocimiento consular confirma operativamente el 29/10/2026: renovación únicamente con DNI vencido o con 60 días o menos de vigencia restante; con más de 60 días no corresponde. La renovación procedente puede incorporar rectificación de datos. Esto no confirma tasa conjunta, tasa única, acumulación de tasas ni exoneración. No se presenta como comprobación normativa externa ni como texto del PDF original.

Se actualizan únicamente los bloques generales de `dni_mayor_renovacion.txt` y `dni_mayor_rectificacion.txt`, con procedencia diferenciada en sus cabeceras. Son los dos consumidores directos de esa relación; se evita un octavo documento o duplicarla en los otros cinco TXT. Se conservan tasas y requisitos particulares. El corpus sigue teniendo siete documentos y 43 fragmentos; el contenido de dos bloques cambia y exige reconstrucción del índice. La inspección existente compara automáticamente todos los bloques actuales, sin añadir otra lista de reglas.

No se extiende esta política a menores, amarillo a azul ni a la combinación de renovación con estado civil, todavía no autorizada por las reglas específicas.

## Causas confirmadas

1. El estado adulto solo distinguía vencido/vigente. El plan relacionaba renovación y rectificación únicamente por vencimiento y no representaba el umbral operativo ahora confirmado.
2. La renovación adulta individual pasaba por generación LLM y el verificador general no cotejaba la lista completa de obligaciones. Un proveedor simulado que añadió DNI anterior, importe de 14 euros, cuatro fotografías o certificado de domicilio conservaba su salida. No se modifica el corpus para legitimar ninguno de esos añadidos.
3. La respuesta combinada informaba tasas individuales, pero podía perder los documentos cuando la pregunta pedía a la vez requisitos y coste, y su explicación sugería dos trámites independientes.

## Implementación y decisiones

- `adult_context.py`: categorías `vencido`, `hasta_60`, `mas_60`; ausencia y `vigente` significan umbral desconocido. Se conserva `vigente` por compatibilidad como «vigente sin días suficientes para decidir». Solo se almacenan categorías, no cifras exactas ni fechas. Dos meses no se convierten en 60 días: el calendario puede variar. Se reconocen cantidades de días/semanas y algunos meses explícitos; el vocabulario no es universal. Contradicciones quedan pendientes.
- El plan mantiene la operación solicitada. Rectificación con vencido/hasta_60 autoriza rectificación y renovación; con mas_60 autoriza solo rectificación. Renovación con mas_60 recupera su regla para explicar que no procede, incluso ante repreguntas de plazo/cita; no se cambia silenciosamente a rectificación.
- Una petición explícita de renovación con rectificación cuya vigencia no se conoce requiere aclarar vencido/60 o menos/más de 60. No se solicita una fecha exacta. El vencimiento ya declarado no vuelve a preguntarse. Las consultas generales de renovación con vigencia desconocida reciben requisitos/tasa condicionados a la elegibilidad, sin afirmar que el ciudadano ya la cumple; no se introduce una pregunta innecesaria para orientar sobre condiciones individuales.
- `classification.py`: una observación de DNI vencido ya no sobrescribe evidencia específica/contradictoria extraída sobre vigencia. Se conservan rechazos y el contexto canónico. Un cambio explícito de operación del mismo titular conserva la vigencia confirmada en su revisión; un cambio de titular la invalida.
- `presentation.py` y `combination_guard.py`: renovación adulta general pasa a salida cerrada, sin llamada LLM. La tasa y el párrafo de dos fotografías se extraen de la regla autorizada; se conserva la fotografía actual y distinta de anteriores, características completas y cita oficial. No se incorpora DNI anterior ni certificado de domicilio; la opción documentada de cambio de dirección se conserva cuando se solicita. Coste, documentación y cita se seleccionan según el tema y se responden juntos si la pregunta solicita coste y documentos. El formato exige la frase de autorización operativa del bloque vigente; si no existe, no inventa la política desde el código.
- La respuesta combinada explica que corresponde renovar por vigencia y que puede incorporar la rectificación. Mantiene partida original apostillada/12 meses y alternativa de copia certificada consular, incluida la incertidumbre sobre su antigüedad. Distingue las tasas individuales del importe aplicable al caso: no afirma pago obligatorio de dos tasas.
- `dni_graph.py`: sigue verificando la presentación final. Si el control devuelve MISSING, se marca abstención aunque el estado de recuperación previo dijera disponible; nunca se considera una plantilla incompleta como respuesta factual verificada.
- Cuatro archivos de pruebas anteriores adaptan únicamente las expectativas de llamada LLM para renovación adulta (ahora cero) y la nueva aclaración de vigencia en una combinación antes no resuelta. Se conservan sus casos, fuentes, continuidad y aislamiento.

## Ejemplos

| Consulta | Antes | Ahora |
|---|---|---|
| Adulto: renovar, coste y documentos | El proveedor podía añadir «documento de identidad anterior» | Tasa individual €7 y dos fotografías con sus características; enlace oficial. Elegibilidad condicional si la vigencia no se conoce |
| Renovar, vence en 60 o 59 días | No había categoría de umbral | Renovación procedente; se conserva el procedimiento |
| Renovar, vence en 61 días | Podía ofrecer requisitos sin evaluar procedencia | «Con más de 60 días de vigencia, no corresponde renovar el DNI…» |
| Rectificar nacimiento, DNI vencido, requisitos y coste | Requisitos podían perderse frente al tema coste | Explica renovación con rectificación incorporable; documentos de rectificación autorizados, €7 por cada procedimiento individual, sin importe conjunto confirmado ni obligación de dos pagos |
| Renovación con rectificación, vigencia desconocida | Abstención genérica de combinación | Pregunta por el intervalo necesario, no por la fecha exacta; conserva operación y tema al responder |

## Evidencia de pruebas

Antes de la corrección productiva: **9 fallos y 1 aprobada** entre las diez primeras pruebas nuevas; fallaban 59/60/61 días, seis meses, el bloqueo de cuatro añadidos hostiles y la renovación no procedente.

Suite final: **658 aprobadas, 6 de integración excluidas, 12 advertencias, 10,26 s**, Python 3.11/Linux, sin OpenAI real. Se conservan los 622 casos anteriores y se añaden 36 en `tests/test_renewal_validity.py`.

Se cubren umbrales inclusivos; vencido; meses y desconocido; negación y contradicción de vigencia; días de otro documento/cita; rectificación con y sin renovación; coste y requisitos juntos; aclaración contextual; renovación rechazada; cambios de titular y sesiones independientes, conservación de vigencia al cambiar de operación del mismo titular y opción de cambio de dirección; fuente operativa exigida para la plantilla; verificador ante borradores hostiles. La batería completa conserva RuleIntegrity, índices FAISS temporales con vectores artificiales, reglas ausentes/obsoletas/contradictorias, seguridad, privacidad, concurrencia, menores, amarillo a azul y los procedimientos adultos previos.

No se reconstruye ni modifica el índice de aplicación durante estas pruebas. No se actualizan dependencias ni credenciales.

## Windows / Conda y FAISS

Detener el servidor y respaldar el directorio del índice configurado antes de reemplazarlo. Git no cambia el índice ignorado al actualizar la rama.

```powershell
git fetch origin
git switch feature/dni-mayor-ampliacion
git pull --ff-only origin feature/dni-mayor-ampliacion
conda activate tfm-piloto
$env:GRADIO_ANALYTICS_ENABLED="False"
$env:PYTHONDONTWRITEBYTECODE="1"
python -B -m pytest -q --tb=short -p no:cacheprovider
python -c "from app.rag.index_builder import crear_indice_faiss; print(crear_indice_faiss())"
python -m app.rag.inspect_rules
python -m app.ui
```

La reconstrucción usa el proveedor real de embeddings y las credenciales locales existentes; no se ejecutó aquí. La inspección sin --consulta no usa OpenAI. Comprobar siete TXT, 43 fragmentos y coincidencia de todas las reglas actuales, sin versiones conflictivas. Reiniciar el proceso para usar el índice reconstruido.

Validar localmente el caso de adulto de 45 años; renovación a 59/60/61 días; rectificación con DNI vencido y con más de 60 días; pregunta mixta de coste y requisitos; rechazo de renovación; cambio a menor y repreguntas de cita/plazo/seguimiento. No utilizar datos personales reales. Linux usa los mismos comandos Python después de activar el entorno y variables con export.

## Límites y compatibilidad

No se cambian contratos API ni categorías de métricas. La falta de umbral no se confunde con elegibilidad confirmada. No se calculan fechas exactas, calendarios ni vigencia por documentos externos. El reconocimiento lingüístico es acotado; expresiones no reconocidas necesitan aclaración. La pregunta por nacionalidad peruana y las reservas de otros supuestos permanecen.

Las respuestas generales de renovación adulta y las combinaciones tienen control determinista final; otros procedimientos individuales conservan sus controles anteriores. `ok` no acredita fidelidad factual universal. Queda pendiente validación Windows/Conda, reconstrucción local con embeddings reales y conversación Gradio/OpenAI. La confirmación operativa del usuario no sustituye una verificación normativa externa.
