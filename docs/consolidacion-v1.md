# Consolidación V1: contexto canónico y DNI amarillo a azul

## Base e integración

Se actualizaron referencias remotas explícitas (el fetch configurado inicialmente solo traía la rama de clasificación). Base de esta consolidación: `feature/v1-dni-amarillo-azul` en `53433e5`, incluida su corrección documental preexistente. No se cambió ningún documento durante esta tarea.

Se aplicó `git cherry-pick e777e39`, generando `2e20e63`. El único conflicto estaba en `extraer_evidencia`: se conservaron tanto las señales de amarillo/azul (`referencia_azul`, `tiene_amarillo`, `nunca_tuvo_dni`) como la distinción entre operación afirmativa y observación de tenencia. La invalidación de edad al aclarar un documento se integró sin conflicto. Se conservaron catálogo documental, filtro exacto de fuentes, formularios de aclaración y respuestas contextuales existentes.

## Incompatibilidad encontrada y ajuste

Tras integrar, las 337 pruebas acumuladas pasaron. Se añadieron ocho regresiones de interacción; una falló: tras rechazar amarillo/azul, «Mi hijo tiene 17 años y necesita cambiar DNI amarillo a azul, ya tiene DNI» no rehabilitaba la operación aunque contenía una petición inequívoca.

El detector genérico de operaciones afirmativas no conocía `amarillo_a_azul`. Se ajustó `extraer_evidencia` para reconocer la transición específica afirmativa, usando las cláusulas positivas y el detector de color existentes, sin rehabilitar por mera tenencia. La extracción afirmativa genérica usa `operation_text`, conservando las máscaras de azul por primera vez y actualización de domicilio.

## Archivos respecto a la base remota

- `app/graph/classification.py`: cherry-pick más adaptación de la afirmación específica amarillo/azul.
- `app/graph/context_policy.py`: invalidar edad heredada cuando solo se confirma el rol documental, manteniendo RAG bloqueado hasta aclarar.
- `tests/test_context_policy.py`: diez regresiones de los dos P2, preservando pruebas anteriores.
- `tests/test_v1_extension.py`: ocho casos de interacción: dos peticiones afirmativas con tenencia tras rechazo; cinco repreguntas durante ambigüedad de documento/titular (coste, fotografías, requisitos, cita, plazo); una aclaración de tipo DNI que no borra el rechazo de renovación.
- `docs/estabilizacion-p2-final.md`: informe histórico incorporado del commit original; su apartado de integración posterior queda realizado en esta rama por esta consolidación.
- `docs/consolidacion-v1.md`: este informe.

## Resultado ejecutado

Linux, Python 3.11.17, entorno virtual existente, sin instalar dependencias:

```bash
GRADIO_ANALYTICS_ENABLED=False XDG_CACHE_HOME=/tmp/tfm-cache PYTHONDONTWRITEBYTECODE=1 env -u OPENAI_API_KEY -u TFM_OPENAI_API_KEY .venv/bin/python -B -m pytest -q --tb=short -p no:cacheprovider
```

**345 aprobadas, 6 de integración excluidas, 12 advertencias de dependencias; 10,06 segundos.** Total: 327 de la rama anterior, diez incorporadas del PR #2 y ocho de interacción. No se debilitaron expectativas existentes.

| Área | Evidencia determinista conservada o añadida |
|---|---|
| Primera inscripción y renovación del menor | Rutas documentales separadas, tarifa y cita del menor |
| Amarillo a azul | Procedimiento específico, fuente exacta, €7, fotografías, cita y plazo del corpus |
| Adultos | Clasificación interna y abstención documental |
| Negaciones | Rechazo persistente; solo afirmación suficiente rehabilita |
| Titular/documento | Rol documental no confirma edad; repreguntas no desbloquean RAG |
| Memoria y aclaraciones | Tema conservado, resolución incremental, cambios explícitos |
| Seguridad y persistencia | Suite HTTP, credenciales de sesión, privacidad, concurrencia, TTL y borrado de checkpoints |

## Límites y validación local

No se ejecutó OpenAI real, embeddings, reconstrucción de FAISS ni validación nativa Windows/Conda. El corpus, recuperación FAISS, prompts, verificador, seguridad, sesiones, Gradio, endpoints, credenciales y dependencias no cambiaron respecto a `53433e5`. La rama V2 no se incorporó. `main` y la rama del PR #2 permanecen intactas.

Los proveedores simulados comprueban el flujo, las fuentes y las puertas de autorización documental; no garantizan calidad lingüística de OpenAI ni recuperación semántica real. El clasificador sigue siendo determinista y pide aclaración ante evidencia insuficiente.

Preparado para revisión y repetición de validación Windows/Conda Python 3.11:

```powershell
git fetch origin
git switch feature/v1-dni-amarillo-azul
git pull --ff-only origin feature/v1-dni-amarillo-azul
conda activate tfm-piloto
$env:GRADIO_ANALYTICS_ENABLED="False"
$env:PYTHONDONTWRITEBYTECODE="1"
python -B -m pytest -q --tb=short -p no:cacheprovider
python -m app.ui
```

Repetir manualmente los dos P2 y los diálogos amarillo/azul con preguntas de coste, requisitos, fotografías, cita y plazo. Para validar recuperación real, usar un índice local correspondiente al corpus de cuatro documentos de esta rama; los índices ignorados no se actualizan al cambiar de rama. Mantener separadas las pruebas reales con OpenAI de la suite determinista. No se fusiona `main` con esta entrega.
