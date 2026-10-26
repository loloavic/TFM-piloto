# PR #4: reconocimiento del titular en rectificación

## Causa raíz y reproducción

Base: `1e3217b`, rama `feature/dni-mayor-ampliacion`.

La consulta «Soy mayor de edad y necesito rectificar mi fecha de nacimiento en el DNI, pero el documento está vencido. ¿Qué requisitos debo presentar y cuánto cuesta?» perdió la evidencia **en `solicitante()`**, antes de crear el contexto:

1. El reconocimiento inicial detectaba `soy mayor de edad` y marcaba solicitante propio.
2. `own_dni` solo reconocía peticiones como renovar/tramitar/solicitar/obtener/sacar mi DNI. No incluía rectificar un dato propio en el DNI.
3. La presencia de `presentar` activaba el filtro de personas de apoyo y asignaba `own=False`, aunque se refería a presentar requisitos.
4. Sin solicitante propio, no se reconocía la categoría adulta. `extraer_evidencia()` entregaba titular/edad vacíos.
5. La transición canónica exigía edad; `ruta_documental()` bloqueaba correctamente la recuperación. No era un fallo de FAISS ni de OpenAI, y `verificacion=ok` no certificaba clasificación correcta.

Se escribieron primero once casos de regresión y se ejecutaron antes de modificar producción: **7 fallidos y 4 aprobados**. La prueba de la consulta exacta falló en la comprobación directa de `solicitante()`. Se añadieron después controles de apoyo, parentesco, negaciones y edad numérica.

## Corrección mínima

- `app/graph/classification.py`, `solicitante()`: reconoce objetos propios de rectificación/corrección (DNI o datos propios vinculados al DNI) antes de aplicar el filtro de presentación documental. Se excluyen peticiones negadas. No basta con que el hablante se declare adulto para atribuirle un DNI de apoyo.
- La misma función reconoce padre/madre como sujeto directo de una petición de rectificación de su DNI **solo con una afirmación explícita de adulto/mayor de edad**. El parentesco por sí solo no prueba la edad; no se agrega identidad ni un nuevo tipo persistente.
- `tests/test_adult_dni.py`: dieciséis casos nuevos, incluido recorrido por extractor, transición, ruta, grafo y fuentes, además de repreguntas y cambios adulto/menor.
- Este informe documenta la reproducción, límites y validación local.

No se modificaron `extraer_evidencia()`, transiciones, estado canónico, `ruta_documental()`, contrato de fuentes ni políticas de tasas: la evidencia corregida permite que funcionen como estaban diseñados. Tampoco se cambiaron seguridad, privacidad, sesiones, Gradio, endpoints, TXT, splitter, FAISS, credenciales, dependencias, prompts o verificador factual.

## Comportamiento comprobado

| Caso | Resultado |
|---|---|
| Consulta exacta reportada | Titular propio adulto, operación rectificación, condición vencido; fuentes de rectificación y renovación |
| Soy mayor de edad y quiero rectificar mi DNI | Edad reconocida; aclaración del tipo de modificación si falta |
| Soy adulto y necesito corregir mi fecha de nacimiento | Edad propia reconocida; sin atribuirla automáticamente a un DNI no mencionado, se aclara el documento |
| Tengo 45 años y necesito rectificar datos de mi DNI vencido | Edad adulta reconocida sin guardar 45; conserva rectificación; «datos» genérico puede requerir concretar la modificación |
| Mi padre es mayor de edad y necesita rectificar su DNI | Adulto por afirmación explícita; no por parentesco |
| Soy menor de edad y necesito rectificar mi DNI | Menor; no se autorizan fuentes adultas |
| Necesito rectificar mi DNI sin edad | Conserva solicitud, pide edad, sin recuperación documental |
| Adulto que aporta DNI para acompañar a un menor | No transfiere su edad al menor |
| No soy mayor; soy menor y rectifico mi DNI | Respeta la negación y la edad afirmativa |
| Requisitos/tasa/documentación en turnos siguientes | Mantiene la operación y las fuentes autorizadas |
| Cambio adulto → menor → adulto | Fuentes de cada titular, sin mezclar procedimientos |
| Falta la fuente de renovación en la combinación | Sin fuentes ni generación; abstención documental |

El tema único existente prioriza coste cuando la misma intervención pregunta requisitos y tasa. La respuesta determinista aclara que las fichas no documentan total combinado; una repregunta de requisitos recupera las reglas correspondientes. No se amplía aquí el tratamiento de múltiples temas en un turno ni se infiere una suma de tasas.

## Ejecución

```bash
GRADIO_ANALYTICS_ENABLED=False XDG_CACHE_HOME=/tmp/tfm-cache PYTHONDONTWRITEBYTECODE=1 env -u OPENAI_API_KEY -u TFM_OPENAI_API_KEY .venv/bin/python -B -m pytest -q --tb=short -p no:cacheprovider
```

Resultado final en Linux/Python 3.11.17: **413 aprobadas, 6 de integración excluidas, 12 advertencias de dependencias; 12,11 segundos**. La batería incluye los 397 casos anteriores y dieciséis nuevos. Los proveedores están simulados; no se ejecuta OpenAI real ni la búsqueda semántica del índice real. Las pruebas existentes de seguridad, privacidad, sesiones, concurrencia, negaciones, amarillo/azul y selección documental se conservan.

## Repetición en Windows/Conda

Con árbol limpio, desde el repositorio local:

```powershell
git fetch origin
git switch feature/dni-mayor-ampliacion
git pull --ff-only origin feature/dni-mayor-ampliacion
conda activate tfm-piloto
python --version
$env:GRADIO_ANALYTICS_ENABLED="False"
$env:PYTHONDONTWRITEBYTECODE="1"
python -B -m pytest -q --tb=short -p no:cacheprovider
python -m app.ui
```

Reutilizar el índice de siete documentos que ya se empleó para validar el PR #4: **no se requiere reconstruirlo**, pues TXT y segmentación no cambian. Si el índice local es de una versión anterior del corpus, corresponde actualizarlo por ese motivo independiente, no por esta corrección.

En una conversación nueva, introducir la consulta exacta, comprobar intención `dni_adulto_rectificacion`, fuentes `dni_mayor_rectificacion.txt` y `dni_mayor_renovacion.txt`, y ausencia de pregunta de edad. Repreguntar requisitos/documentación/tasa, cambiar explícitamente a renovar DNI de hijo menor y volver al titular adulto. Confirmar que no se afirma un total combinado. Repetir en otra sesión para comprobar independencia.

La validación nativa Windows/Gradio con OpenAI y FAISS reales debe repetirse localmente; no se declara realizada en esta entrega. El reconocedor sigue siendo determinista: objetos o roles ambiguos deben aclararse y nunca justifican heredar una edad no confirmada. No se modifica main ni se fusiona el PR.
