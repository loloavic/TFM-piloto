# Cierre de F1–F4 y F6 — PR #4

Fecha: 28/10/2026. Base auditada: d5f2e96. Rama: feature/dni-mayor-ampliacion. No se modifica main, no se fusiona PR #4 ni se cambia su estado de borrador.

## Causas y política de integridad

F1: la selección semántica validaba archivo y marcador, pero no el bloque contra el corpus vigente. F2: el primer par archivo/regla ocultaba duplicados posteriores. Se centraliza el control en `app/rag/rule_integrity.py`, usado por el grafo y la lectura exacta.

La autorización del plan canónico precede a la validación. Se exige un bloque completo no vacío de hasta 1800 caracteres, archivo autorizado, marcador coherente con metadata.regla si existe, chunk entero correspondiente al bloque actual e id coherente si existe. Los bloques se comparan con la versión vigente del TXT; no basta con su nombre. El inventario de referencia rechaza marcadores incompletos o repetidos. No se han cambiado los siete TXT.

| Situación | Resultado |
|---|---|
| Regla completa, vigente y metadata coherente | Se acepta evidencia indexada |
| Duplicado idéntico | Una evidencia, sin conflicto |
| Versiones diferentes del mismo par, en cualquier orden | Bloqueo del par y abstención si era obligatorio |
| Bloque obsoleto, vacío, incompleto o metadata incoherente observado | Bloqueo durante la consulta; ni reintento ni respaldo rehabilitan ese par |
| Regla simplemente ausente del ranking | Reintentos finitos existentes y luego lectura exacta autorizada |
| Exacta presente, vigente y sin conflictos | Responde desde docstore, distancia null |
| Ausente del índice o inválida en exacta | Abstención; no se responde desde TXT |
| Otro procedimiento/archivo | No es evidencia autorizada |

Los TXT solo sirven como referencia de integridad. No aportan una respuesta de respaldo. Se conserva el rechazo por par durante todos los reintentos de una consulta; sus códigos internos solo contienen archivo/regla autorizados y causa, nunca texto libre. El estado `rechazos_documentales` y `abstencion_documental` permiten diagnóstico. La lista devuelta por exacta sigue siendo compatible y transporta las causas de rechazo para el grafo.

La validación cubre resultados observados; no se escanea todo el índice en cada consulta semántica completa. Una versión distinta fuera de los resultados observados requiere la inspección global del índice. El índice y corpus son artefactos locales confiables, no cargas de usuarios; mantenerlos de solo lectura para clientes y actualizar/reiniciar fuera de consultas activas. No es una firma criptográfica ni una garantía de vigencia normativa externa.

## Métricas y contratos

F3: la lista antigua reducía intenciones nuevas a general y toda abstención a observada. `log_service.py` deriva ahora el catálogo de intenciones de DOCUMENTADOS más general/fuera_alcance. Mantiene los siete campos CSV existentes, preguntas/respuestas vacías y fuentes []. Verificación se persiste como ok, observada o abstencion_documental, sin incluir detalles libres. Valores desconocidos conservan el fallback histórico observada/general.

No cambia el esquema de API ni la cabecera de sesión. `verificacion` de la consulta conserva su detalle y valores actuales. Los resúmenes admiten categorías de cadena; abstencion_documental aparece separada. `consultas_observadas` sigue contando solo observada: no se cambia silenciosamente su significado para incluir abstenciones. Los consumidores deben sumar ambas categorías si necesitan todas las consultas no ok.

n8n/Sheets que transportan las mismas columnas no requieren un mapeo nuevo. Filtros o listas cerradas deben admitir las nuevas categorías (adultos, amarillo a azul y abstencion_documental). No hay workflows versionados en este repositorio para ejecutar su validación real. Los CSV anteriores no se reescriben: sus categorías ya colapsadas no pueden reconstruirse sin evidencia que no se conserva. Separar periodos/versiones de medición; no comparar conteos históricos como si tuvieran idéntica clasificación.

## Verificación y presentación

F4: no se introduce un verificador universal. `ok` indica ausencia de incidencias en los controles disponibles; no demuestra exactitud factual general. Gradio muestra explícitamente esa limitación, manteniendo intacto el valor API. Los controles deterministas de combinaciones, reglas comunes y viudez italiana conservan su alcance; otros casos mantienen generación LLM y controles existentes.

F6: README y guía principal consolidan el estado; los informes previos quedan identificados como históricos. La confirmación operativa italiana y las disposiciones comunes no se atribuyen al PDF original. Subsisten reservas en otros países/nacionalidades y límites lingüísticos como la pregunta sobre nacionalidad italiana tras mencionar nacionalidad peruana; no inferir exclusividad de nacionalidad.

## Archivos y pruebas

- `rule_integrity.py`: validador compartido y resultados con diagnóstico.
- `exact_rules.py`, `dni_graph.py`, `state.py`: integración, rechazo acumulado y abstención.
- `inspect_rules.py`: reutiliza el patrón común; sigue disponible sin embeddings.
- `log_service.py`: categorías sin datos personales.
- `ui.py`: aclaración visible del significado de verificación.
- Nuevos `test_rule_integrity.py` y `test_metrics_categories.py`: 28 casos. Dos fixtures antiguas de clasificación/V1 pasan a usar los fragmentos reales en lugar de todo el TXT; no se eliminan ni relajan sus expectativas funcionales.
- README, guía principal e informes históricos: estado y trazabilidad.

Reproducción previa a cambios productivos: **10 fallos y 10 aprobadas** entre las primeras 20 pruebas nuevas. Fallaban obsolescencia, vacío, metadata, contradicciones en ambos órdenes y categorías adultas/amarillo/abstención. Tras la corrección se añaden casos de docstore FAISS contradictorio en ambos órdenes, rechazo sin rehabilitación, archivo no autorizado, contradicción entre reintentos, resúmenes y aclaración de UI.

Resultado final de suite completa: **601 aprobadas, 6 de integración excluidas, 12 advertencias de dependencias**. Se conservan los 573 casos previos. Linux/Python 3.11, sin OpenAI real; FAISS temporal real con vectores artificiales en las pruebas que lo necesitan. Índice de aplicación no modificado; sin nuevas dependencias. No se valida Windows nativo ni servicios n8n/Sheets reales.

## Windows / Conda y despliegue

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

No se requiere reconstrucción por este cambio de código si las reglas ya coinciden con los siete TXT actuales (43 fragmentos). Ante índice obsoleto: detener aplicación, respaldar el índice configurado y reconstruir usando las credenciales locales ya existentes. No alterar ni publicar .env.

```powershell
python -c "from app.rag.index_builder import crear_indice_faiss; print(crear_indice_faiss())"
python -m app.rag.inspect_rules
python -m app.ui
```

La reconstrucción sí consume embeddings reales: no se ejecutó aquí. Inspección sin --consulta no utiliza OpenAI. Linux usa los mismos comandos tras activar el entorno; variables mediante export.

Repetir localmente renovación/rectificación, viudez italiana y otros supuestos, plazo/seguimiento/advertencias y cambio a menor. Comprobar categorías en métricas y consumidores. La validación real restante es de despliegue/proveedor e integraciones; no sustituye las garantías deterministas ni certifica exactitud universal.
