# PR #3: sincronización controlada con main

Se fusiona `origin/main` (`f14f69c`, integración del PR #2) en `feature/v1-dni-amarillo-azul`, partiendo de `8a8f6d7`. Se conserva el historial mediante un commit de fusión; no se modifica directamente main, no se incorpora V2 ni se fusiona el PR #3.

## Conflictos y archivos

Único archivo conflictivo: `app/graph/classification.py`, en dos bloques de `extraer_evidencia`:

- La extracción genérica de operación afirmativa de main frente a la adaptación de la rama funcional que utiliza `operation_text` y reconoce la petición afirmativa de amarillo a azul.
- Las señales `referencia_azul`, `tiene_amarillo`, `nunca_tuvo_dni`, presentes únicamente en la rama funcional.

Se conservan los bloques de la rama funcional, que ya incluyen las correcciones de `e777e39`. `context_policy.py` se fusiona automáticamente sin diferencias respecto a la rama funcional, conservando la invalidación de edad heredada y la persistencia de rechazos. No se aplican de nuevo los parches ni se duplican pruebas.

Tras resolver, el árbol de aplicación, pruebas, corpus y dependencias es idéntico a `8a8f6d7`, comprobado con `git diff --exit-code`. El único archivo nuevo respecto a ese commit es este informe. No se añaden pruebas porque no hay comportamientos nuevos.

## Verificación del corpus

Los cuatro TXT existen y se compararon byte a byte con `8a8f6d7`:

| Archivo | SHA-256 |
|---|---|
| dni_amarillo_a_azul_primera_vez.txt | 28774ab5aef49dbfdfacd114f53646a45b2cf68b187a2f1d2972a900e6b5ab20 |
| dni_consulta_estado.txt | adb4a62de224aaa2ec770f0af365ca23e3848ad3bb7805f4fbd8d94a7d9ecbd4 |
| dni_menor_primera_vez.txt | bc4a21cdd5a5642f20ae08e0bf6876e797ae6273b3ebd05928177879eb435fa3 |
| dni_menor_renovacion.txt | 4b872fce39320cd8c27da9a3f2cc017017771c3c38e5259064912226d3437860 |

No se modifican credenciales, `.env`, seguridad, sesiones, Gradio, endpoints, FAISS ni corpus.

## Pruebas ejecutadas

Linux, Python 3.11.17, entorno existente:

```bash
GRADIO_ANALYTICS_ENABLED=False XDG_CACHE_HOME=/tmp/tfm-cache PYTHONDONTWRITEBYTECODE=1 env -u OPENAI_API_KEY -u TFM_OPENAI_API_KEY .venv/bin/python -B -m pytest -q --tb=short -p no:cacheprovider
```

**345 aprobadas, 6 de integración excluidas, 12 advertencias de dependencias, 9,57 s.** Se mantienen las regresiones acumuladas, incluidos los dos P2 de contexto y su interacción con amarillo/azul, seguridad, sesiones y concurrencia. `git diff --check` y la comprobación del índice no detectaron errores de formato.

No se ejecutó OpenAI real, reconstrucción del índice ni validación nativa en Windows. Los proveedores simulados verifican el flujo y las fuentes, no la calidad lingüística ni la recuperación semántica real.

La inclusión de `f14f69c` como ancestro elimina la divergencia con la versión de main comprobada. El PR #3 queda preparado para revisión sin conflictos de contenido con esa versión; aprobaciones, CI y políticas de GitHub son comprobaciones independientes. Si main avanza de nuevo, debe verificarse otra vez.
