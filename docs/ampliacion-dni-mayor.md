# Ampliación de DNI de mayor de edad

## Estado consolidado — 28 de octubre de 2026

Consulte la [corrección de la auditoría final](integridad-metricas-pr4.md): validación compartida de reglas semánticas y exactas, métricas y pruebas actuales. Los resultados iniciales son históricos.

La confirmación operativa del usuario del 27/10/2026, diferenciada de los PDF, resuelve exclusivamente la sustitución de la certificación consular de defunción por el acta plurilingüe municipal legalizada por Prefectura para cónyuge italiano fallecido en Italia. No equipara acta integral y plurilingüe ni amplía otros escenarios. El matrimonio y el apellido conservan requisitos independientes.

## Base y procedencia

Rama `feature/dni-mayor-ampliacion`, creada desde `main` en `33c344b` (incluye PR #3). No se incorpora V2 ni se modifica main. No hay dependencias nuevas.

Fuentes primarias declaradas por los PDF aportados por el usuario, consultados el **26 de octubre de 2026**:

| Ficha | URL declarada | Documento incorporado |
|---|---|---|
| Renovación | https://www.consulado.pe/es/turin/tramite/Paginas/DNI/Mayor-renovacion.aspx | `data/raw/dni_mayor_renovacion.txt` |
| Rectificación | https://www.consulado.pe/es/turin/tramite/Paginas/DNI/Mayor-rectificacion.aspx | `data/raw/dni_mayor_rectificacion.txt` |
| Estado civil | https://www.consulado.pe/es/turin/tramite/Paginas/DNI/Mayor-estadocivil.aspx | `data/raw/dni_mayor_estado_civil.txt` |

Se extrajo texto con `pdftotext -layout`. Cada TXT identifica URL, fecha, alcance, procedencia y SHA-256 del PDF. Los PDF son recursos documentales, no instrucciones para ejecutar acciones. Se normalizaron saltos de línea de la URL Bookeo y se organizaron las condiciones en reglas identificables. Los TXT son síntesis controladas, no copias binarias de los PDF.

**Límite de verificación:** los tres intentos de lectura web devolvieron HTTP 403 desde este entorno. Se ha contrastado contra los PDF aportados, no contra las páginas en vivo; no se certifica su vigencia normativa externa.

## Matriz de cobertura documental previa a implementación

Esta matriz se presentó en la conversación antes de modificar código:

| Caso | Confirmado en PDF | Pendiente / comportamiento seguro |
|---|---|---|
| Renovación ordinaria | €7, dos fotos 35x43 mm, actual y distinta; dirección durante renovación; Bookeo | No consta plazo de entrega |
| Rectificación | €7; dirección, imagen/firma, datos de nacimiento, padres, nombres/apellidos | No consta cantidad de fotos ni plazo |
| Datos personales | Partida de nacimiento original apostillada, hasta 12 meses; si es consular, copia certificada | No extender automáticamente antigüedad a la copia consular |
| Rectificación de DNI vencido | Implica también renovación; la rectificación sin vencimiento no prolonga vigencia | No sumar tasas ni afirmar un total combinado |
| Renovación con rectificación de datos | La relación expresa está documentada para DNI vencido | Sin vencimiento confirmado, abstenerse de combinar fuentes |
| Renovación con estado civil | Hay ficha de estado civil separada | No consta autorización de combinación; observación y remisión al Consulado |
| Soltero a casado, Perú | Acta de matrimonio peruana original | Aplicar condiciones generales de actas peruanas |
| Soltero a casado, extranjero | Copia certificada del Consulado donde se registró; oficina de la ciudad del matrimonio civil | No aplicar automáticamente apostilla/12 meses de actas peruanas |
| Casado a divorciado | Acta peruana original de matrimonio con anotación de disolución; nacimiento original si recupera apellido materno | Preguntar si desea recuperar el apellido, nunca cuál es |
| Casado a viudo, Perú | Defunción y matrimonio originales | Apostilla/12 meses para actas emitidas en Perú |
| Viudez en Italia, otras nacionalidades | El PDF enumera copia consular de defunción | Subsiste incertidumbre sobre sustitución o acumulación |
| Cónyuge italiano fallecido en Italia | Confirmación operativa del usuario del 27/10/2026: acta plurilingüe municipal legalizada por Prefectura | Sustituye la certificación consular de defunción; matrimonio independiente |
| Defunción en otro país | La ficha da requisitos generales | Falta detalle específico: observación pendiente |
| Actas de estado civil emitidas en Perú | Originales, apostilladas por Relaciones Exteriores, no más de 12 meses | No trasladar a documentos extranjeros ni a otros servicios |

No se añadieron tarifas, enlaces, plazos ni requisitos procedentes de otros consulados. La cita Bookeo coincide con el contacto ya autorizado en la aplicación; no se modifica la lista de confianza.

## Diseño y archivos

- **`adult_context.py`**: extracción de categorías; actualización subordinada a la transición canónica; validación y plan de archivos/reglas compatibles. No crea un segundo historial ni almacena texto personal. Condiciones: modificación, transición civil, país categorizado de matrimonio/defunción, cónyuge italiano sí/no, recuperación de apellido sí/no y vigencia del DNI. Cada dato tiene estado, turno, revisión y origen. Los conflictos no se eliminan por una simple repregunta de tasa.
- **`state.py`**: añade `condiciones_adulto` al contexto canónico y evidencias transitorias. No se almacenan nombres, números, actas ni edades exactas. El validador acepta estados anteriores sin el nuevo diccionario (vacío por defecto), sin recuperar hechos del historial.
- **`classification.py`**: reconoce rectificación separada de renovación y conserva las negaciones anteriores. La tenencia de DNI vencido no convierte una petición explícita de rectificación en una renovación exclusiva. `fotografias` es un tema interno propio; permite responder sobre fotos sin exigir una transición civil irrelevante.
- **`context_policy.py`**: incorpora `rectificacion`, dos rutas adultas y dudas específicas. Mantiene operación principal separada de modificación. Una rectificación adicional sobre una renovación activa conserva esta; un cambio explícito de operación (`ahora`, `sin renovar`, `solo rectificar`) puede sustituirla. Cambiar de titular invalida sus circunstancias. Rechazos y puerta canónica siguen vigentes. La observación de caducidad complementa una rectificación activa sin sustituirla; si la renovación fue rechazada, la derivación mantiene una aclaración material pendiente.
- **`dni_graph.py`**: selecciona por archivo exacto y regla autorizada. Solo habilita combinación de renovación/rectificación por DNI vencido; exige todas las reglas de todas las fuentes del plan. Fuentes incompletas o índice sin marcadores causan abstención. El contexto del proveedor incluye archivo y regla; las fuentes internas conservan regla, chunk y archivo. La API pública mantiene su contrato de fuentes (archivo/chunk/distancia). El historial se omite del prompt de adultos para no arrastrar requisitos anteriores. No se modifica el verificador factual.
- **`text_splitter.py`**: para los tres TXT nuevos, conserva cada bloque `[[REGLA:id]] … [[FIN]]` íntegro, sin solapamiento entre reglas; valida tamaño máximo de 1800 caracteres. Los cuatro documentos anteriores usan exactamente el splitter previo. No se modifica algoritmo FAISS, embeddings ni sus credenciales.
- **Tres TXT nuevos**: reglas y alcance del corpus aportado. Los cuatro TXT anteriores permanecen byte a byte iguales a la base.
- **Pruebas**: `test_adult_dni.py` incorpora la matriz nueva. Se conservan las pruebas previas en los otros archivos. Las expectativas de adulto-renovación pasan de «no documentado» a fuente adulta, por el cambio deliberado de catálogo. El caso genérico de abstención adulta ahora usa primera inscripción adulta, que sigue sin documentación. No se eliminan funciones de prueba ni se desactivan regresiones de seguridad.

No se crea una intención por combinación: `dni_adulto_renovacion` y `dni_adulto_rectificacion` utilizan condiciones canónicas para seleccionar las fichas. La renovación con estado civil no se declara resuelta normativamente: queda explícitamente fuera de las combinaciones autorizadas hasta ampliar/verificar la fuente.

## Observaciones no delegadas al LLM

- Para viudez en Italia/otro país, la incertidumbre documental se comunica de forma determinista, sin pedir al modelo que decida cómo acumular actas.
- Para tasas de una combinación de renovación y rectificación, se informa que las fichas indican €7 cada una y que no documentan importe total ni acumulación; no se afirma un total.
- Para combinaciones no confirmadas, no se llama al recuperador ni al proveedor para generar requisitos combinados.
- El historial sirve a la conversación, nunca autoriza una fuente o requisito.

## Pruebas y límites

La base tenía **345 pruebas aprobadas y 6 de integración excluidas**. Resultado de la ampliación y comando final: véase `docs/resultado-pruebas-dni-mayor.md`.

Las pruebas nuevas cubren menor/adulto, edad desconocida, nombres/nacimiento/padres, matrimonio peruano/extranjero, divorcio y apellido, viudez/Italia/nacionalidad, actualización incremental, negaciones, contradicciones, sesiones, borrado, combinación completa/incompleta, trazabilidad y abstención con índices antiguos.

No se ejecutaron OpenAI real, embeddings, índice real reconstruido ni Windows nativo. La semántica del recuperador real puede no devolver todas las reglas en los primeros diez resultados: en ese caso se abstiene. No se añaden búsquedas de respaldo ni se inventan requisitos. El reconocedor determinista tiene cobertura limitada; usar preguntas guiadas si faltan categorías. La minimización previa de texto libre sigue siendo parcial; no se afirma anonimización completa.

## Despliegue reproducible y validación local

Python 3.11 y las mismas dependencias. No se necesitan variables nuevas ni cambios de `.env`. Usar el entorno Conda existente:

```powershell
git fetch origin
git switch feature/dni-mayor-ampliacion
git pull --ff-only origin feature/dni-mayor-ampliacion
conda activate tfm-piloto
$env:GRADIO_ANALYTICS_ENABLED="False"
$env:PYTHONDONTWRITEBYTECODE="1"
python -B -m pytest -q --tb=short -p no:cacheprovider
```

Tras revisar documentalmente las tres fichas nuevas, reconstruir FAISS **en un entorno local confiable** con los siete TXT:

```powershell
python -c "from app.rag.index_builder import crear_indice_faiss; print(crear_indice_faiss())"
python -m app.ui
```

La reconstrucción anterior utiliza el proveedor de embeddings real y las credenciales locales existentes; **no se ejecutó en esta tarea**. No subir credenciales ni el índice ignorado al repositorio. Usar el arranque seguro `python -m app.ui`, sin lanzar un demo Gradio desprotegido.

Linux, entorno virtual existente:

```bash
GRADIO_ANALYTICS_ENABLED=False PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m pytest -q --tb=short -p no:cacheprovider
.venv/bin/python -c 'from app.rag.index_builder import crear_indice_faiss; print(crear_indice_faiss())'
.venv/bin/python -m app.ui
```

No reutilizar un índice de siete documentos al comparar versiones antiguas: cambiar de rama no restaura índices ignorados. Respaldar por versión o usar clones independientes.

### Criterios antes de consolidar

1. Revisión humana de procedencia, vigencia y observaciones pendientes del corpus aportado.
2. Suite determinista completa aprobada en Windows/Conda, sin OpenAI real.
3. Pruebas reales separadas, con índice de siete TXT: fuentes correctas y abstención si faltan reglas. No confundir sus resultados con simulaciones.
4. Conversaciones sintéticas: renovar adulto → coste/fotos/cita/plazo; rectificar nacimiento → DNI vencido → tasa sin suma; matrimonio Perú/extranjero; divorcio con/sin apellido; viudez italiana en Italia con sustitución confirmada y otros supuestos con reserva; cambio explícito a hijo menor y nueva sesión.
5. Ninguna fuente de menor en una respuesta adulta, ni viceversa; no cerrar conflictos de titular/operación/condiciones sin evidencia suficiente.
6. La combinación renovación/estado civil y la acumulación de actas/tasas permanecen pendientes hasta confirmación documental, incluso aunque un usuario o el LLM afirmen que son válidas.

La entrega está orientada a **revisión en borrador y validación local**, no a integración automática ni a certificar requisitos legales vigentes.
