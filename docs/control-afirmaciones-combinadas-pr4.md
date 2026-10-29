# PR #4: control de afirmaciones documentales combinadas

> Evidencia histórica de su entrega. El estado consolidado, pruebas y correcciones posteriores se describen en [integridad y métricas del PR #4](integridad-metricas-pr4.md). Los resultados de este informe corresponden a su versión.


Fecha: 27 de octubre de 2026. Base: `faa9b7e`, rama `feature/dni-mayor-ampliacion`.

## Causa confirmada y reproducción

La protección anterior solo respondía determinísticamente cuando `tema == coste`. Después de la consulta inicial, una repregunta de documentación o fotografías entraba de nuevo al generador. El contexto incluía dos fichas con tasas y requisitos individuales, pero no un contrato normativo de acumulación. El modelo podía sintetizar una «tasa única» o trasladar la cantidad de fotografías de renovación a la combinación.

El prompt ya decía «No sumes tasas». Esto no era una garantía ejecutable. El verificador anterior solo comprobaba indicios generales (correo inesperado, número de DNI y aclaraciones); no verificaba tasas ni condiciones. Por ello, una respuesta incorrecta podía recibir `ok`.

Se escribieron y ejecutaron antes de modificar producción siete regresiones: **las siete fallaron**. Tres reprodujeron la generación indebida tras cambiar de tema y cuatro comprobaron que borradores con tasa única, total inventado, exoneración o eliminación de documentos seguían pasando por el verificador.

## Corrección por archivo

- **`app/graph/combination_guard.py`**: compositor determinista sin llamadas al proveedor. Recalcula la autorización desde `ruta_documental()` y el plan canónico, y comprueba la presencia de todas las reglas requeridas, sin admitir reglas ajenas ni duplicados de contenido contradictorio. Para combinaciones autorizadas de renovación y rectificación ofrece información individual atribuida, sin sintetizar obligaciones conjuntas. Las combinaciones no autorizadas reciben la explicación limitada existente; la ausencia de reglas produce abstención.
- **`app/graph/dni_graph.py`**, redactor: aplica el compositor antes de decidir qué tema enviar al LLM. Elimina la excepción anterior que solo protegía coste. La selección RAG, clasificación, contexto y orden del grafo no cambian.
- **Mismo archivo, verificador**: recalcula de forma independiente la respuesta permitida. Si el borrador difiere, lo sustituye y emite `observada: Borrador sustituido por el control determinista de alcance documental combinado.` La respuesta final, el borrador persistido y el nuevo turno del historial contienen el texto corregido. No se confía en una bandera que el generador pueda afirmar.
- **`tests/test_combination_grounding.py`**: proveedores hostiles, inyección directa de borradores en el verificador, cambio de temas, procedimientos individuales, combinaciones civiles no autorizadas y fuentes faltantes.
- **`tests/test_adult_dni.py`**: dos casos previos de combinación actualizan su expectativa de llamada al proveedor: ahora deben obtener el requisito individual respaldado sin invocar al LLM. No se eliminan esos casos ni se relajan las comprobaciones de fuentes.
- **README e informe**: alcance, evidencia y repetición local.

Los siete TXT permanecen iguales. No se modifican credenciales, dependencias, prompts, verificación de sesiones, privacidad, Gradio, API, embeddings, FAISS, clasificación, memoria ni selección de fuentes. Sí se modifica deliberadamente el control de salida y la comprobación de su borrador antes del historial.

## Qué garantiza el código

| Ámbito | Control ejecutable |
|---|---|
| Tasas de combinación | Extrae únicamente la tasa individual de cada regla general autorizada; no calcula suma, tasa única, exoneración ni importe total |
| Requisitos | Cita las reglas específicas individuales, como la partida original apostillada o la alternativa consular, atribuyendo su fuente; no las convierte en lista conjunta definitiva |
| Fotografías | Presenta los párrafos individuales como citas y explica que no confirman cantidad conjunta; no transforma las dos fotos de renovación en obligación de la combinación |
| Citas y plazo | No garantiza una reserva conjunta por compartir enlace ni inventa plazo combinado |
| Fuentes incompletas | No emite requisitos o tasas conjuntos; abstención |
| Combinación civil no autorizada | No usa al LLM para completar la regla ausente |
| Borrador indebido en ámbito restringido | Sustitución determinista, estado observado y escritura del texto seguro en el historial |

No hay una lista negra de frases con la que se intente reconocer todas las paráfrasis de «tasa única». Todo borrador distinto del texto permitido se sustituye en este ámbito, aunque use otras cifras, sinónimos o sea aparentemente prudente. El objetivo es una respuesta de alcance cerrado, no evaluar semánticamente cualquier frase libre.

Para requisitos se conserva información útil: la partida de nacimiento exigida por la ficha de rectificación se sigue proporcionando como requisito **de esa ficha individual**. La aclaración de alcance no obliga a bloquear toda la respuesta. Las condiciones fotográficas individuales se citan por separado; esa cita no autoriza acumulación, sustitución o aplicabilidad automática al supuesto combinado.

## Qué no queda garantizado

- No es un verificador factual universal de lenguaje libre. Los procedimientos individuales y otros temas mantienen el generador y controles anteriores.
- El control presupone un corpus e índice confiables. No certifica vigencia normativa de los PDF ni corrige una fuente errónea.
- `verificacion: ok` en una respuesta determinista significa que no fue necesario sustituirla y que no se detectaron los avisos existentes. No certifica que el Consulado haya aprobado una combinación. La propia respuesta declara esa limitación.
- Las respuestas incorrectas que ya existan en un historial anterior no se borran retroactivamente. El control evita nueva síntesis normativa combinada a partir de ellas; se conservan la política de sesiones y retención.
- No se han incorporado reglas de tasa combinada ni documentos nuevos para resolver lo que las fichas no establecen.

## Ejecución y cobertura

Comando utilizado, Linux/Python 3.11.17:

```bash
GRADIO_ANALYTICS_ENABLED=False XDG_CACHE_HOME=/tmp/tfm-cache PYTHONDONTWRITEBYTECODE=1 env -u OPENAI_API_KEY -u TFM_OPENAI_API_KEY .venv/bin/python -B -m pytest -q --tb=short -p no:cacheprovider
```

Resultado final: **437 aprobadas, 6 de integración excluidas, 12 advertencias de dependencias; 13,51 segundos**. Se conservan los 413 casos anteriores y se añaden 24 casos de control de salida: tres repreguntas hostiles, doce combinaciones de borrador indebido y tema, ciclo de temas, seis procedimientos individuales, combinación civil y fuente faltante. Las seis pruebas de integración externa siguen excluidas.

Los cuatro procedimientos previos están incluidos: primera inscripción y renovación de menor, consulta de estado y amarillo/azul. También renovación adulta con €7 individual documentado, rectificación individual y combinación sin total confirmado. El proveedor hostil está configurado para emitir condiciones falsas si se le llama; la composición restringida impide esa llamada. La prueba del verificador simula además la llegada directa de esos borradores, para no depender únicamente del bloqueo previo.

No se ejecutaron OpenAI real, FAISS real, reconstrucción del índice ni validación Windows nativa.

## Windows/Conda y validación real

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

No se requiere reconstruir el índice existente de siete documentos: corpus y segmentación no cambian. Con el índice correcto y una sesión nueva, repetir la consulta inicial reportada, la repregunta de fecha de nacimiento, tasas y fotografías. Deben mantenerse la intención y las fuentes adultas, la información individual de la partida y la explicación de límites, sin tarifa conjunta ni cantidad fotográfica conjunta confirmada. Cambiar a renovación adulta ordinaria y comprobar su tasa individual; repetir los cuatro procedimientos anteriores en conversaciones nuevas.

La forma más rígida de la respuesta combinada es una decisión deliberada: la fluidez no puede autorizar condiciones que el corpus no establece. `main` no se modifica y el PR no se fusiona.
