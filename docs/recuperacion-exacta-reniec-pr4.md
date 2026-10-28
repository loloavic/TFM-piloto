# PR #4: recuperación exacta de reglas autorizadas

> Evidencia histórica de su entrega. El estado consolidado, pruebas y correcciones posteriores se describen en [integridad y métricas del PR #4](integridad-metricas-pr4.md). Los resultados de este informe corresponden a su versión.


27 de octubre de 2026. Base `dfa4af1`; rama `feature/dni-mayor-ampliacion`.

## Causa confirmada y límites de la investigación

El mecanismo anterior hacía una búsqueda semántica top‑10 y reintentos semánticos añadiendo archivo/regla a la pregunta. Esos términos **no son un filtro de metadata**: no garantizan que FAISS devuelva el fragmento necesario. No existía una vía de lectura exacta del índice después de autorizar el par archivo/regla.

Se escribió primero una reproducción con seguimiento en una conversación de viudez y ranking que omite la regla: falló antes de cambiar producción, pues no se utilizaba la recuperación exacta y se mantenía la abstención. Se verificó después el caso con FAISS local real y vectores artificiales: tanto búsqueda inicial como reintento excluyen la regla del top‑10, aunque está en el docstore y puede recuperarse exactamente.

El corpus actual contiene los siete TXT y produce **43 fragmentos**. En los tres archivos adultos, `seguimiento` conserva ambos marcadores y se fragmenta íntegramente con metadata de archivo/chunk. Se verifica en pruebas, incluyendo la ficha civil. No se modificaron TXT ni fragmentador.

**No se ha leído el índice de Windows ni se ha ejecutado su ranking OpenAI.** No se afirma que se haya demostrado el origen exacto de su omisión particular. Un total de 43 fragmentos no acredita por sí solo que todas las reglas estén presentes, completas o vigentes. Se proporciona un diagnóstico local para distinguir las causas.

## Corrección mínima por archivo

- `app/rag/exact_rules.py`: lectura del docstore del mismo índice FAISS, sin embeddings ni consulta semántica. Revalida `ruta_documental()` y el plan canónico; rechaza solicitudes fuera del conjunto autorizado antes de abrir el índice. Recorre los documentos referenciados por el índice y selecciona solo bloques completos del archivo y regla solicitados, con chunk válido y metadata coherente. Contrasta el bloque con el TXT actual para no utilizar versiones desactualizadas. **El TXT se usa para validar integridad, nunca para responder si falta el bloque en el índice.** No modifica ni reconstruye el índice.
- `app/graph/dni_graph.py`: después de los reintentos acotados anteriores, realiza **una sola consulta exacta por turno**, agrupando los pares aún faltantes. Vuelve a filtrar los resultados por el plan, conserva la exigencia de completitud y el diagnóstico `reglas_faltantes`. No aumenta `k` ni introduce un bucle ilimitado.
- `app/rag/inspect_rules.py`: diagnóstico local sin embeddings por defecto; compara el índice con los bloques actuales. La opción explícita `--consulta` ejecuta dos búsquedas semánticas y muestra solo archivo/chunk/reglas/distancia, no cuerpos documentales ni conversaciones.
- `app/models.py`: añade a las fuentes `recuperacion` y admite `distancia=null` en lectura exacta. No inventa una distancia de similitud para una lectura por clave. Las fuentes semánticas conservan su distancia numérica.
- `app/ui.py`: representa correctamente distancia numérica o lectura exacta sin distancia; no cambia autenticación ni estado de navegador.
- `tests/conftest.py`: aísla la nueva frontera de lectura del índice personal en pruebas unitarias. Las pruebas específicas la sustituyen por índices temporales controlados; no se leen índices privados accidentalmente. No se altera la ejecución explícita de pruebas marcadas como integración.
- `tests/test_exact_rule_retrieval.py`: veintiún casos nuevos; conserva los 517 anteriores.

### Compatibilidad de trazabilidad

La fuente exacta mantiene archivo y chunk reales del índice y añade `recuperacion: exacta`; su distancia es `null`. La semántica se identifica como `semantica`. Clientes externos que formateen `distancia` deben admitir `null` y mostrar el método. Gradio y FastAPI están cubiertos por pruebas. Esta extensión no modifica contratos de credenciales ni cuerpos de solicitud.

## Distinción de causas

| Evidencia local | Interpretación |
|---|---|
| Regla íntegra, coincide con TXT; no aparece en inicial/reintento | Omisión del ranking; la lectura exacta autorizada puede resolverla |
| `ausente_del_indice` | No se encontró un bloque válido con ese par; no se suple desde TXT |
| Fragmento adulto en `fragmentos_invalidos` | Marcadores incompletos/estructura no reconocida; revisar fragmentación y versión del índice |
| `distinta_del_txt_actual` | Bloque con contenido diferente; posible índice obsoleto, modificado o construido desde otra versión; exacta se abstiene |
| `versiones_conflictivas` | Más de una versión en el docstore; revisar/reconstruir desde el corpus aprobado |
| Ruta de índice no legible | Revisar la ubicación usada al arrancar y la integridad de archivos; el diagnóstico local hace visible el error |

El diagnóstico compara con el corpus local, no certifica vigencia jurídica externa. Una entrada no legible o una regla inválida no autorizan a inventar seguimiento o disponibilidad. La comparación estricta puede abstenerse ante versiones con diferencias de formato: se prefiere revisar el índice a mezclar versiones.

## Pruebas ejecutadas

Comando completo, Linux/Python 3.11.17:

```bash
GRADIO_ANALYTICS_ENABLED=False XDG_CACHE_HOME=/tmp/tfm-cache PYTHONDONTWRITEBYTECODE=1 env -u OPENAI_API_KEY -u TFM_OPENAI_API_KEY .venv/bin/python -B -m pytest -q --tb=short -p no:cacheprovider
```

**Resultado final: 538 aprobadas, 6 de integración excluidas, 12 advertencias de dependencias; 8,52 segundos.** Los casos nuevos cubren regla fuera del ranking; docstore de 43 fragmentos; archivo/regla no autorizados; contexto inválido; ausencia, truncamiento, bloque vacío, otra regla y contenido desactualizado; matriz de tres procedimientos adultos por plazo/advertencias/seguimiento; trazabilidad en FastAPI/Gradio; inventario completo e independencia del proveedor de embeddings.

Las pruebas construyen y leen **índices FAISS temporales reales con vectores artificiales**. No se reconstruyó el índice de la aplicación, no se ejecutó OpenAI y no se probó Windows nativo. La suite anterior conserva seguridad, privacidad, sesiones, documentos de menores, amarillo/azul y control determinista de combinaciones. No se modifican esas políticas, corpus ni modelos de embeddings.

El control de seguimiento sigue respondiendo desde la regla autorizada y afirma que el 100 % no es garantía automática de disponibilidad para entrega. El acceso exacto no autoriza nuevas condiciones normativas.

## Windows/Conda: actualizar y diagnosticar antes de reconstruir

```powershell
git fetch origin
git switch feature/dni-mayor-ampliacion
git pull --ff-only origin feature/dni-mayor-ampliacion
conda activate tfm-piloto
$env:GRADIO_ANALYTICS_ENABLED="False"
$env:PYTHONDONTWRITEBYTECODE="1"
python -B -m pytest -q --tb=short -p no:cacheprovider
python -m app.rag.inspect_rules
```

El último comando no usa OpenAI. Revisar `dni_mayor_estado_civil.txt#seguimiento`: debe indicar `coincide_con_txt_actual`, con bloque íntegro y conteos correspondientes. Si la aplicación utiliza otra ubicación, indicar `--indice` y, si procede, `--documentos`.

Para inspeccionar los rankings del caso con el proveedor real, ejecutar **opcionalmente** (utiliza las credenciales locales existentes y consume embeddings):

```powershell
python -m app.rag.inspect_rules --consulta "Ya han pasado cuatro meses desde mi trámite. ¿Cómo puedo consultar el estado de mi DNI y saber si está disponible para recogerlo?" --archivo dni_mayor_estado_civil.txt --regla seguimiento
```

Comprobar `ranking.inicial` y `ranking.reintento`: si ambos omiten el par pero el inventario lo confirma, el fallo es de selección semántica, no ausencia del documento. No introducir datos personales reales para este diagnóstico.

**No es necesario reconstruir por esta corrección:** se aprovechan contenido y metadata existentes del índice de 43 fragmentos. Si el diagnóstico muestra reglas ausentes/desactualizadas/inválidas, revisar primero ubicación y versión. Solo entonces reconstruir con el corpus aprobado, según las instrucciones previas. El código no genera una fuente desde el TXT para ocultar un índice incompleto.

Reiniciar con `python -m app.ui`, abrir una conversación nueva, resolver viudez y preguntar seguimiento. Debe conservarse `dni_adulto_rectificacion`, ficha civil, regla `seguimiento`, y mostrarse lectura exacta cuando el ranking no la devuelva. Repetir después de renovación y rectificación; confirmar el límite de disponibilidad al 100 %.

## Riesgos residuales

La lectura exacta recorre el docstore local y escala con su tamaño; es razonable para el piloto de 43 fragmentos. Se añade una lectura de disco cuando los métodos semánticos fallan, pero no embeddings ni búsquedas ilimitadas. No se habilita acceso a checkpoints ni fuentes ajenas; se utiliza únicamente el índice local confiable ya previsto por el proyecto.

La comprobación contra TXT requiere desplegar el corpus junto al código, como en el piloto actual. Un índice de otra versión se abstiene hasta corregirlo. El índice real de Windows y el ranking real siguen pendientes de inspección local; las simulaciones no acreditan su contenido. `main` no se modifica ni se fusiona el PR #4.
