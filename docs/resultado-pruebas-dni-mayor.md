# Resultado ejecutado: ampliación DNI adulto

Entorno: Linux, Python 3.11.17, entorno virtual existente. Sin instalación de dependencias, sin OpenAI real ni embeddings reales.

```bash
GRADIO_ANALYTICS_ENABLED=False XDG_CACHE_HOME=/tmp/tfm-cache PYTHONDONTWRITEBYTECODE=1 env -u OPENAI_API_KEY -u TFM_OPENAI_API_KEY .venv/bin/python -B -m pytest -q --tb=short -p no:cacheprovider
```

Resultado final: **397 passed, 6 deselected, 12 warnings in 11.39s**.

- Los 345 casos previos se siguen recogiendo. Se ajustaron las expectativas que declaraban inexistente la documentación de renovación adulta, ahora incorporada. Ninguna función de prueba anterior fue eliminada. El caso de abstención genérica de adulto se mantiene con primera inscripción adulta, todavía fuera del corpus, y la renovación adulta está cubierta por los casos de clasificación y fuentes.
- Se añaden 52 casos deterministas en `tests/test_adult_dni.py`: clasificación menor/adulto; edad desconocida; datos personales; dirección e imagen/firma; matrimonio en Perú/extranjero; divorcio y recuperación de apellido; viudez y condiciones de Italia; preguntas sucesivas de tasa/fotos/cita/plazo; aclaraciones guiadas; cambios y contradicciones de condiciones; rechazo de renovación; caducidad que complementa rectificación; fuentes combinadas completas e incompletas; API autorizada; eliminación e independencia de sesiones; validación del splitter y abstención con índices sin marcadores.
- La matriz de la batería anterior sigue cubriendo seguridad HTTP, sesiones, privacidad, concurrencia, expiración y checkpoints. Sus archivos de seguridad no se modificaron.
- Las seis pruebas marcadas como integración se excluyen conforme al `pytest.ini` existente.
- Las doce advertencias proceden de dependencias (deprecaciones de LangChain/Starlette/Pandas/Gradio); no se actualizaron dependencias para ocultarlas.

## Evidencia adicional

- Comparación byte a byte de los cuatro TXT anteriores con `33c344b`: iguales.
- Comparación AST de `verificar_respuesta` y `construir_grafo_dni` con la base: iguales.
- Comparación de archivos protegidos (API, modelos públicos, core/seguridad, servicios/sesiones, UI, recuperador FAISS, constructor de índice y dependencias): sin cambios.
- `git diff --check`: sin errores.
- El splitter mantiene reglas nuevas completas y usa el comportamiento anterior en los cuatro TXT previos.

## Defectos de integración detectados durante el desarrollo

Las nuevas pruebas detectaron que las preguntas solo sobre fotografías civiles exigían innecesariamente datos de matrimonio/divorcio, y que una aclaración de edad podía perder el tema de coste. Se separó el tema interno `fotografias` y se respetó `consulta_pendiente` al determinar qué condiciones hacen falta.

También se cubrió explícitamente la observación de caducidad durante una rectificación: no sustituye la operación, solo habilita la derivación documentada. Una renovación rechazada conserva el bloqueo hasta recibir una solicitud afirmativa, incluso cuando el documento está vencido.

Las preguntas con alternativas incompatibles de lugar o modificación generan conflicto canónico; una repregunta de coste no lo cierra. La ausencia de una regla o una de las fichas de una combinación provoca abstención.

## No ejecutado

Validación nativa Windows/Conda, generación real con OpenAI, reconstrucción FAISS y recuperación semántica contra un índice real. Los proveedores simulados permiten comprobar transiciones, prompts, selección de fuentes y ausencia de llamadas durante bloqueos, no la calidad lingüística ni la cobertura semántica del proveedor real.
