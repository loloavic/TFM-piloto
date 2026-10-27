# PR #4: estabilización de viudez y disposiciones generales

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
