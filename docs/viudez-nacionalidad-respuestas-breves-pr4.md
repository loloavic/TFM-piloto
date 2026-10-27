# PR #4: viudez, nacionalidad y respuestas breves

27 de octubre de 2026. Base `357ef51`, rama `feature/dni-mayor-ampliacion`.

## Causas confirmadas y reproducción

1. La extracción de `italiano` solo reconocía una referencia al cónyuge seguida de «era/es italiano». No admitía «ciudadano italiano» ni «de nacionalidad italiana». Tampoco interpretaba respuestas elípticas como «Sí, era italiano» sin repetir «mi esposo».
2. El estado ya admitía respuestas binarias para nacionalidad o recuperación de apellido, pero Gradio rechazaba menos de tres caracteres y FastAPI imponía `min_length=3`. Por ello, «sí», «si» y «no» no llegaban al grafo desde esas interfaces.

Se escribieron doce reproducciones antes de modificar producción: **nueve fallaron y tres pasaron**. Los tres aciertos correspondían a respuestas binarias directamente en el servicio, mostrando que parte de la lógica contextual ya existía; la validación del transporte impedía aprovecharla.

## Corrección por archivo

- **`app/graph/adult_context.py`**: separa nacionalidad con sujeto explícito (esposo/esposa/cónyuge) de respuestas elípticas. Admite era/es, ciudadano/a y de nacionalidad. Las respuestas ampliadas se aplican solo a viudez con defunción en Italia, cuando la nacionalidad está pendiente o ya existe para poder corregirla. Una referencia a padre/madre no confirma nacionalidad del cónyuge. Un «no» explícito en «no, era peruano» responde negativamente; no se infiere exclusión de ciudadanía italiana solo por mencionar otra nacionalidad. Los valores opuestos en una misma declaración se convierten en conflicto canónico y bloquean recuperación hasta aclarar.
- **`app/graph/classification.py`**: transmite la categoría transitoria `respuesta_nacionalidad`. No transmite ni persiste el texto de la aclaración en ese campo.
- **`app/graph/state.py`**: añade ese campo a `EvidenciaTurno`, no un nuevo dato persistente. El contexto conserva el mismo `italiano=si/no` o conflicto, con turno, revisión y origen.
- **`app/core/query_validation.py`**: validación léxica compartida de entradas. Mantiene 3–1000 caracteres para consultas ordinarias y admite exclusivamente sí/si/no como excepción de dos caracteres. Rechaza vacío, espacios, un carácter, otras cadenas de dos caracteres, solo signos y exceso de longitud.
- **`app/models.py`**: `min_length=2` permite pasar las respuestas breves al validador de campo, que aplica la excepción restringida. El esquema describe esa excepción; no se aceptan arbitrariamente todas las entradas de dos caracteres.
- **`app/ui.py`**: usa la misma validación antes de invocar al servicio, conservando el estado privado y el manejo de autorización. También aplica el máximo de 1000 caracteres ya existente en FastAPI.
- **`tests/test_widow_answers.py`**: treinta y ocho casos nuevos; no se modifica ni elimina ninguna prueba anterior.

No se modifican los siete TXT, FAISS, prompts, selector de reglas, control determinista de combinaciones, endpoints, tokens, cookies, exclusión mutua, retención ni eliminación de checkpoints. No se instalan dependencias ni se modifican credenciales.

## Resolución contextual y alcance

- La consulta completa «Mi esposo falleció en Italia y era ciudadano italiano» confirma nacionalidad sin preguntar de nuevo.
- Si falta la decisión sobre recuperar apellido materno, esa pregunta sigue siendo necesaria: confirmar nacionalidad no confirma apellido. No se pide el apellido real.
- «sí»/«si»/«no» responden únicamente a la dimensión binaria pendiente. Si la pregunta es apellido, no se convierten en una respuesta de nacionalidad.
- «Era italiano», «si era italiano», «Sí, era italiano», «era ciudadano italiano» y «no, era peruano» resuelven la aclaración nacional pertinente.
- Una corrección explícita «Me equivoqué, no era italiano» actualiza el dato sin borrar viudez, lugar de defunción ni titular adulto.
- La contradicción mantiene la recuperación bloqueada, incluso si después se pregunta el coste. No se selecciona una rama arbitrariamente.
- Sin contexto, una respuesta breve admitida léxicamente no autoriza una fuente ni confirma una condición. El asistente pide aclarar el trámite.
- Las referencias a otra persona, la ausencia de reglas del índice y los cambios de titular conservan el comportamiento restrictivo. Se mantienen las advertencias de las actas en Italia; reconocer nacionalidad no resuelve su sustitución o acumulación documental.

La nueva categoría transitoria no almacena nacionalidad peruana, identidad, nombres ni texto personal. El dato persistente sigue siendo la condición italiana sí/no necesaria para seleccionar reglas. El historial y su minimización parcial son los existentes; no se afirma anonimización total de texto libre.

## Resultado ejecutado

Linux, Python 3.11.17, entorno virtual existente:

```bash
GRADIO_ANALYTICS_ENABLED=False XDG_CACHE_HOME=/tmp/tfm-cache PYTHONDONTWRITEBYTECODE=1 env -u OPENAI_API_KEY -u TFM_OPENAI_API_KEY .venv/bin/python -B -m pytest -q --tb=short -p no:cacheprovider
```

**488 aprobadas, 6 de integración excluidas, 12 advertencias de dependencias; 12,40 segundos.** Son los 450 casos anteriores, sin alterar sus expectativas, y 38 casos nuevos.

Cobertura nueva: consultas completas y ampliadas; sí/si/no; API HTTP y callback Gradio; validación inválida equivalente; otra aclaración binaria (apellido); correcciones y contradicciones; continuidad; cambio de titular; sesiones independientes; autorización requerida incluso para «sí»; abstención si falta la regla italiana. La suite anterior conserva los controles HTTP de Gradio, privacidad, concurrencia, sesiones y todos los procedimientos DNI.

No se ejecutaron OpenAI real, búsqueda FAISS real ni Windows nativo. Las comprobaciones de Gradio de este archivo llaman al callback Python; no son una prueba manual del navegador. Las pruebas HTTP de seguridad/concurrencia existentes también se ejecutaron en la batería completa.

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

No reconstruir el índice por este cambio: los siete TXT y su segmentación siguen iguales.

En una sesión nueva, repetir la consulta completa reportada: debe conservar viudez, Italia y condición italiana afirmativa. Si solicita recuperar apellido materno, responder solo sí/no, sin datos identificativos. En otra conversación, omitir nacionalidad para probar la pregunta y contestar «si era italiano», «Sí, era italiano» o «no, era peruano». Comprobar después requisitos, aviso documental y reglas: `general`, `viudez_italia`, `italiano` solo si corresponde, y `apellido` solo si se confirmó recuperación.

Corregir con «Me equivoqué, no era italiano» y comprobar que desaparece la regla italiana. Probar «a», vacío y «ab»: ambos accesos deben rechazarlos; una sesión ajena no debe aceptar «sí» sin credencial. Repetir el cambio a hijo menor y una conversación independiente.

## Riesgos residuales

El reconocedor sigue siendo determinista y de cobertura limitada: paráfrasis no reconocidas pueden requerir aclaración. No deduce ciudadanía exclusiva a partir de otra nacionalidad. La validación es léxica, no un filtro semántico universal de relevancia; una consulta ordinaria válida puede estar fuera de alcance y será tratada por el clasificador. La aceptación de una palabra breve no constituye autorización ni confirmación sin contexto. La ambigüedad normativa sobre las actas y el carácter parcial de la minimización previa permanecen explícitos.

La entrega actualiza la rama del PR #4 sin fusionarlo ni cambiar su estado de revisión. Main permanece intacta.
