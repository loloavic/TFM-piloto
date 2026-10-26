# Estabilización de los dos P2 sobre 9b6f85a

## Alcance y causas confirmadas

- `classification.py`, `extraer_evidencia`: `solicitud` mezclaba la identificación del destinatario con la afirmación de una operación. «Es para mi hijo…, ya tiene DNI» dejaba de ser observación y podía rehabilitar una renovación rechazada.
- `context_policy.py`, `transicionar`: al resolver una duda documental como DNI del titular solo se invalidaba la edad heredada si no se había reconocido ningún titular. «Mi hijo» reconoce una relación, pero no distingue entre los hijos de edades diferentes introducidos en la conversación.

## Corrección

- `operacion` permite desactivar las inferencias de tenencia manteniendo los mismos detectores de afirmaciones y negaciones. El extractor distingue operación afirmada de operación deducida de tenencia, independientemente de que se haya identificado al destinatario o el rol documental. La política canónica existente conserva el rechazo frente a observaciones.
- Resolver el rol como titular sin nueva evidencia de edad invalida la edad anterior y mantiene una aclaración de edad contradictoria. Si tampoco se identifica el titular, mantiene además esa duda. RAG continúa bloqueado por la puerta canónica existente.
- No se modifican esquema canónico, corpus, FAISS, prompts, verificador factual, seguridad, privacidad, sesiones, UI, endpoints ni dependencias.

## Evidencia y pruebas

Antes de cambiar producción, las siete regresiones iniciales fallaron sobre 9b6f85a: seis combinaciones de los dos escenarios con repreguntas de coste/plazo/cita, y resolución posterior hacia adulto.

Se añaden diez casos en `tests/test_context_policy.py`: los siete anteriores y tres variantes de tenencia/caducidad/rol documental con rechazo persistente y posterior petición afirmativa. Las pruebas del grafo comprueban la continuidad de sesión, ausencia de fuentes y ausencia de nuevas llamadas al recuperador/proveedor durante la ambigüedad. Una confirmación suficiente vuelve a habilitar la ruta del menor; confirmar adulto conserva la abstención documental.

Resultado final en Linux, Python 3.11.17: **305 aprobadas, 6 de integración excluidas, 12 advertencias de dependencias, 10,26 s**. Se conservan las 295 pruebas anteriores sin modificar sus expectativas, incluidas seguridad HTTP, sesiones, concurrencia, TTL y eliminación de checkpoints.

Comando ejecutado:

```bash
GRADIO_ANALYTICS_ENABLED=False XDG_CACHE_HOME=/tmp/tfm-cache PYTHONDONTWRITEBYTECODE=1 env -u OPENAI_API_KEY -u TFM_OPENAI_API_KEY .venv/bin/python -B -m pytest -q --tb=short -p no:cacheprovider
```

No se ejecutó OpenAI real, reconstrucción del índice ni validación nativa en Windows/Conda. No se instalaron dependencias.

## Incorporación posterior a DNI amarillo a azul

La rama `feature/v1-dni-amarillo-azul` no se modifica con esta entrega. Al comprobar el remoto figuraba en `53433e59c2b71083a3120b5e0150af28972f7c7e`, más avanzada que la copia local. Trabajar sobre su versión remota actualizada, con árbol limpio, e incorporar mediante `git cherry-pick` el commit de esta corrección publicado en `fix/dni-classification-context`. No hacer reset ni force-push.

Puede haber conflictos en `classification.py`: conservar las reglas de amarillo/azul y adaptar la extracción de operación afirmativa a esas operaciones; no reemplazar todo el archivo por la versión de PR #2. Preservar el catálogo y las dudas `tipo_dni` de la rama posterior, junto con la invalidación de edad y los rechazos persistentes de esta corrección.

Antes de consolidar:

1. Ejecutar la suite determinista completa de la rama combinada, incluidas estas diez regresiones y todas las pruebas de amarillo/azul, tarifas separadas, contactos oficiales, tipos de DNI ambiguos y negaciones. El total puede crecer con los avances posteriores; no asumir que el total de esta rama es el de la rama combinada.
2. Repetir casos de rechazo y documento/titular en combinación con el cambio amarillo/azul, cambios de titular y aclaraciones `tipo_dni`; verificar que ninguna aclaración parcial habilita RAG.
3. Repetir seguridad, aislamiento, concurrencia, reinicio y eliminación de sesiones.
4. En Windows/Conda Python 3.11, ejecutar `python -B -m pytest -q --tb=short -p no:cacheprovider` y las conversaciones sintéticas de ambos cambios con el arranque seguro `python -m app.ui`.
5. Para validación real del recuperador, usar un índice correspondiente al corpus de cada rama. Los índices locales ignorados no cambian al cambiar de rama. La reconstrucción con embeddings reales queda fuera de esta ejecución.

## Límites

El reconocedor sigue siendo determinista y no garantiza comprensión de cualquier expresión. Ante la confirmación del rol sin edad se prefiere pedir aclaración a usar un titular no confirmado. Las pruebas con proveedor simulado verifican el flujo y las puertas documentales, no la calidad lingüística de OpenAI. La integración con amarillo/azul y la ejecución nativa en Windows requieren las verificaciones anteriores.
