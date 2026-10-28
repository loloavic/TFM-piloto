# Asistente Consular DNI - Piloto TFM

Prototipo funcional de un asistente conversacional basado en LangGraph, RAG y modelos LLM para orientar a ciudadanos en consultas relacionadas con trámites de DNI en una oficina consular.

El sistema clasifica la intención de la consulta, recupera información desde una base documental local, genera una respuesta orientativa, verifica reglas básicas de seguridad y registra trazabilidad de las interacciones.

## 1. Objetivo del prototipo

El objetivo del piloto es validar una arquitectura conversacional capaz de:

- Responder consultas frecuentes sobre trámites de DNI.
- Diferenciar entre renovación de DNI de menor de edad, DNI de menor por primera vez y consulta de estado del trámite.
- Entregar enlaces oficiales de cita o consulta cuando corresponda.
- Evitar solicitar datos personales sensibles, como el número de DNI.
- Rechazar consultas fuera del alcance documental cargado.
- Registrar trazabilidad para evaluación funcional.

## 2. Arquitectura general

El flujo principal del sistema se implementa mediante LangGraph:

```text
Pregunta del ciudadano
→ clasificar_intencion
→ enriquecer_busqueda
→ recuperar_documentos
→ redactar_respuesta
→ verificar_respuesta
→ respuesta_final
```

La recuperación documental se realiza mediante un índice FAISS generado a partir de documentos de texto almacenados localmente en `data/raw`.

El modelo LLM se utiliza para la generación controlada de respuestas, mientras que el grafo define el flujo lógico de procesamiento y permite separar las responsabilidades de clasificación, recuperación, redacción y verificación.

## 3. Estructura del proyecto

La estructura del proyecto se organizó separando la API, la configuración, el flujo LangGraph, los componentes RAG, los servicios auxiliares, los datos fuente, los scripts de evaluación y las pruebas automatizadas.

```text
tfm-piloto/
├── app/
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py
│   ├── graph/
│   │   ├── __init__.py
│   │   ├── state.py
│   │   └── dni_graph.py
│   ├── rag/
│   │   ├── __init__.py
│   │   ├── document_loader.py
│   │   ├── text_splitter.py
│   │   ├── index_builder.py
│   │   └── retriever.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── llm_service.py
│   │   ├── rag_service.py
│   │   ├── log_service.py
│   │   └── evaluation_service.py
│   ├── __init__.py
│   ├── main.py
│   ├── models.py
│   └── ui.py
├── data/
│   ├── raw/
│   │   ├── dni_menor_renovacion.txt
│   │   ├── dni_menor_primera_vez.txt
│   │   └── dni_consulta_estado.txt
│   ├── vector_store/
│   │   └── faiss_index/
│   └── logs/
├── scripts/
│   └── run_evaluation.py
├── tests/
│   └── test_api.py
├── 00_verificacion_entorno.ipynb
├── .env.example
├── .gitignore
├── pytest.ini
├── requirements.txt
└── README.md
```

Los componentes agentivos del sistema fueron implementados como nodos dentro del archivo `app/graph/dni_graph.py`. Por ello, no se utiliza una carpeta independiente de agentes. Esta decisión permite mantener una estructura compacta y suficiente para el alcance del piloto, conservando la separación lógica entre clasificación, recuperación, redacción y verificación.

## 4. Requisitos

Para ejecutar el prototipo se requiere:

- Python 3.11.
- Entorno Conda o virtualenv.
- Clave de API de OpenAI.
- Conexión a internet para las llamadas al modelo LLM.
- Índice FAISS generado previamente.
- Dependencias instaladas desde `requirements.txt`.

## 5. Instalación del entorno

Crear el entorno Conda:

```powershell
conda create -n tfm-piloto python=3.11
```

Activar el entorno:

```powershell
conda activate tfm-piloto
```

Instalar dependencias:

```powershell
pip install -r requirements.txt
```

En caso de no contar todavía con el archivo `requirements.txt`, se pueden instalar las dependencias principales con:

```powershell
pip install fastapi "uvicorn[standard]" gradio
pip install langgraph langchain-openai langchain-community langchain-text-splitters
pip install faiss-cpu pypdf tiktoken python-dotenv pydantic-settings httpx
pip install pytest pytest-asyncio pandas
```

## 6. Configuración

Crear un archivo `.env` en la raíz del proyecto con el siguiente contenido:

```env
OPENAI_API_KEY=tu_clave_openai
OPENAI_MODEL=gpt-4.1-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

El archivo `.env` contiene credenciales sensibles y no debe subirse a repositorios públicos.

El archivo `.env.example` puede conservarse como plantilla sin incluir claves reales.

## 7. Documentos fuente

Los documentos utilizados por el sistema se almacenan en:

```text
data/raw/
```

Documentos incluidos en el piloto:

```text
dni_menor_renovacion.txt
dni_menor_primera_vez.txt
dni_consulta_estado.txt
```

Cada documento contiene información estructurada sobre el trámite correspondiente, incluyendo requisitos, costos, enlaces oficiales, advertencias y condiciones especiales.

La calidad de las respuestas del sistema depende directamente de la calidad, cobertura y actualización de estos documentos fuente.

## 8. Construcción del índice FAISS

Cuando se agreguen o modifiquen documentos en `data/raw`, debe reconstruirse el índice vectorial.

Desde un notebook o consola Python, ejecutar:

```python
from app.rag.index_builder import crear_indice_faiss

total = crear_indice_faiss()
print("Fragmentos indexados:", total)
```

El índice se almacena en:

```text
data/vector_store/faiss_index/
```

Este índice permite realizar la recuperación semántica de fragmentos documentales relevantes para cada consulta del ciudadano.

## 9. Ejecución de la API

Desde la raíz del proyecto:

```powershell
python -m uvicorn app.main:app --reload
```

Luego abrir Swagger en el navegador:

```text
http://127.0.0.1:8000/docs
```

Endpoints principales:

```text
GET  /health
POST /api/v1/consultas
GET  /api/v1/evaluacion/resumen
GET  /api/v1/evaluacion/consultas
```

### Endpoint de consulta

El endpoint principal del asistente es:

```text
POST /api/v1/consultas
```

Ejemplo de cuerpo JSON:

```json
{
  "pregunta": "¿Qué requisitos necesito para renovar el DNI de mi menor hijo?"
}
```

La respuesta incluye:

- Identificador de consulta.
- Pregunta formulada.
- Estado de procesamiento.
- Respuesta generada.
- Intención clasificada.
- Resultado de verificación.
- Fuentes documentales recuperadas.

## 10. Ejecución de la interfaz Gradio

Para ejecutar la interfaz visual:

```powershell
python -m app.ui
```

La interfaz permite formular consultas y visualizar:

- Respuesta del asistente.
- Fuentes documentales recuperadas.
- Intención clasificada.
- Resultado de verificación.

Esta interfaz fue utilizada como mecanismo de prueba manual durante el desarrollo del piloto.

## 11. Flujo LangGraph

El flujo conversacional se define en:

```text
app/graph/dni_graph.py
```

El grafo incluye los siguientes nodos:

| Nodo | Función |
|---|---|
| `clasificar_intencion` | Identifica el tipo de consulta formulada por el ciudadano. |
| `enriquecer_busqueda` | Amplía la pregunta con términos útiles para mejorar la recuperación documental. |
| `recuperar_documentos` | Recupera fragmentos relevantes desde el índice FAISS. |
| `redactar_respuesta` | Genera una respuesta usando el contexto recuperado. |
| `verificar_respuesta` | Aplica reglas básicas de control sobre la respuesta generada. |

Las intenciones consideradas en el piloto son:

```text
dni_menor_renovacion
dni_menor_primera_vez
dni_consulta_estado
fuera_alcance
general
```

## 12. Evaluación funcional

El proyecto incluye un script reproducible de evaluación:

```powershell
python scripts/run_evaluation.py
```

Este script ejecuta seis casos de prueba funcional:

| Código | Caso |
|---|---|
| P01 | Requisitos renovación DNI menor |
| P02 | Cita renovación DNI menor |
| P03 | DNI menor por primera vez |
| P04 | Costo DNI menor primera vez |
| P05 | Consulta de estado |
| P06 | Consulta fuera de alcance |

El script compara la intención esperada con la intención obtenida, verifica el resultado del nodo de validación y calcula la tasa de cumplimiento funcional.

El resultado se exporta en:

```text
data/logs/evaluacion_casos_prueba.csv
```

Ejemplo de salida esperada:

```text
================================================================================
EVALUACIÓN FUNCIONAL DEL ASISTENTE
================================================================================
Casos evaluados: 6
Casos correctos: 6
Tasa de cumplimiento: 100.00%
Archivo generado: data/logs/evaluacion_casos_prueba.csv
================================================================================
```

## 13. Pruebas automatizadas

El proyecto incluye pruebas automatizadas con `pytest`.

Ejecutar desde la raíz del proyecto:

```powershell
pytest
```

Resultado esperado:

```text
8 passed
```

Las pruebas verifican:

- Disponibilidad del servicio mediante `/health`.
- Clasificación de intención para consultas de DNI.
- Respuesta sobre costo de trámite.
- Control de privacidad en consultas de estado.
- Control de consultas fuera de alcance.
- Validación de entradas inválidas.
- Funcionamiento de endpoints de evaluación.

## 14. Trazabilidad

Cada consulta procesada queda registrada en:

```text
data/logs/consultas_log.csv
```

El registro incluye:

- Fecha y hora.
- Pregunta formulada.
- Intención clasificada.
- Resultado de verificación.
- Respuesta generada.
- Fuentes recuperadas.

Este mecanismo permite auditar el comportamiento del asistente durante la fase experimental y facilita la evaluación posterior del piloto.

## 15. Endpoints de evaluación

El sistema incluye endpoints específicos para revisar la ejecución del piloto.

### Resumen de evaluación

```text
GET /api/v1/evaluacion/resumen
```

Devuelve información agregada como:

- Total de consultas registradas.
- Número de consultas fuera de alcance.
- Número de consultas observadas por el verificador.
- Distribución de intenciones clasificadas.
- Distribución de resultados de verificación.

### Detalle de consultas registradas

```text
GET /api/v1/evaluacion/consultas
```

Permite consultar las últimas interacciones registradas.

También acepta el parámetro `limite`:

```text
GET /api/v1/evaluacion/consultas?limite=6
```

## 16. Archivos de log

Los archivos de log se almacenan en:

```text
data/logs/
```

Archivos principales:

```text
consultas_log.csv
evaluacion_casos_prueba.csv
```

Estos archivos no deben subirse a repositorios públicos, ya que pueden contener preguntas reales formuladas por usuarios durante las pruebas.

## 17. Privacidad y seguridad

El asistente está diseñado para evitar la captura de datos personales sensibles.

En particular:

- No solicita números de DNI.
- No consulta directamente bases de datos oficiales.
- No almacena credenciales en el código fuente.
- Redirige al ciudadano al portal oficial correspondiente cuando la consulta requiere ingresar datos personales.
- Restringe sus respuestas a la información disponible en las fuentes documentales cargadas.

Para consultas de estado del DNI, el sistema orienta al ciudadano a realizar la consulta directamente en el portal oficial de RENIEC.

## 18. Limitaciones del piloto

El prototipo tiene las siguientes limitaciones:

- Está limitado a la documentación cargada localmente.
- No consulta información oficial en tiempo real.
- No valida datos personales del ciudadano.
- No reemplaza la atención oficial de la oficina consular.
- Las respuestas son orientativas.
- La calidad de la respuesta depende de la calidad de los documentos fuente.
- El verificador implementado utiliza reglas básicas y no sustituye una auditoría formal.

Estas limitaciones son coherentes con el alcance experimental del piloto.

## 19. Control de alcance

El sistema incorpora una intención específica para consultas fuera del dominio documental:

```text
fuera_alcance
```

Por ejemplo, ante la consulta:

```text
Necesito renovar mi pasaporte.
```

El asistente debe responder indicando que no cuenta con información suficiente en las fuentes cargadas y que el piloto está limitado a consultas relacionadas con trámites de DNI.

Esto evita que el sistema genere respuestas sobre trámites no contemplados en el alcance del prototipo.

## 20. Generación de `requirements.txt`

Para actualizar el archivo de dependencias:

```powershell
pip freeze > requirements.txt
```

Este archivo permite reproducir el entorno de ejecución del proyecto en otra máquina.

## 21. Archivos excluidos del repositorio

El archivo `.gitignore` debe incluir:

```gitignore
.env
__pycache__/
*.pyc
.pytest_cache/
.ipynb_checkpoints/
data/vector_store/*
data/logs/*
```

Esto evita subir claves, cachés, índices vectoriales y trazas de consultas.

## 22. Comandos principales

Resumen de comandos útiles:

```powershell
conda activate tfm-piloto
```

```powershell
python -m uvicorn app.main:app --reload
```

```powershell
python -m app.ui
```

```powershell
python scripts/run_evaluation.py
```

```powershell
pytest
```

## 23. Estado del prototipo

El prototipo cuenta con:

- Backend FastAPI funcional.
- Flujo LangGraph operativo.
- Recuperación documental mediante FAISS.
- Generación de respuestas mediante LLM.
- Interfaz Gradio.
- Registro de trazabilidad.
- Endpoints de evaluación.
- Script reproducible de evaluación.
- Pruebas automatizadas con `pytest`.

## 24. Consideraciones finales

Este prototipo constituye una prueba funcional de una arquitectura conversacional basada en LangGraph y RAG aplicada a la orientación de ciudadanos en trámites de DNI en contexto consular.

El sistema no busca reemplazar los canales oficiales, sino demostrar la viabilidad técnica de un asistente capaz de reducir consultas repetitivas, orientar al ciudadano hacia el trámite correcto, entregar enlaces oficiales y evitar la captura innecesaria de datos personales.
## Endurecimiento de seguridad y privacidad — fase 1

Consultar [el contrato, variables y política de retención](docs/seguridad-fase-1.md)
antes de desplegar esta rama. La consulta inicial sigue siendo pública; continuar
una conversación requiere ahora `session_id` y la cabecera `X-Session-Token`
recibida en la primera respuesta. Los endpoints de evaluación requieren un secreto
administrativo y los registros nuevos no guardan preguntas ni respuestas.

La minimización de texto es parcial: no debe describirse como anonimización.
Los ejemplos de evaluación y el número de pruebas de las secciones anteriores
corresponden al piloto original; no constituyen resultados de esta fase. Por
defecto `pytest` ejecuta las pruebas deterministas sin OpenAI. Las seis pruebas
que requieren proveedor e índice se seleccionan con `pytest -m integration`.

### Correcciones de segunda revisión R1–R5

La entrada soportada de Gradio sigue siendo `python -m app.ui`, ahora con una
frontera HTTP adicional de cookie y namespaces de sesión. No publicar
`demo.launch()` directamente. La coordinación es por hilo, las métricas fallidas
no revocan conversaciones válidas y un vencimiento durante la consulta devuelve
410 sin credencial. Los contactos oficiales aprobados se conservan en las
salidas. Ver [instrucciones Windows/Conda y Linux, políticas y límites](docs/seguridad-fase-1.md).

## Fase 1B.1–1B.2: clasificación y continuidad conversacional

La clasificación distingue trámite activo, tema de la pregunta y categoría del
titular. Las repreguntas sobre plazo, coste y cita conservan el procedimiento;
las menciones de documentos de apoyo no se tratan automáticamente como un
trámite distinto. Si falta edad u operación se pide aclaración; los trámites de
adultos identificados no reciben requisitos de menores ni amplían el corpus.
Ver [modelo de estado, compatibilidad, pruebas y límites](docs/clasificacion-contexto-1b.md).

### V1: DNI amarillo a azul y fluidez conversacional

La ampliación desde `9b6f85a` se desarrolla en `feature/v1-dni-amarillo-azul`.
La [guía V1 de ampliación](docs/v1-dni-amarillo-azul.md) describe las fuentes
separadas, la tasa de €7, las mejoras acotadas de conversación, las pruebas y
la actualización Windows/Conda. Requiere reconstruir el índice local después
de verificar el corpus; para comparar con V1 debe utilizarse su índice correspondiente.

### Ampliación de DNI de mayor de edad (en revisión)

La rama `feature/dni-mayor-ampliacion` incorpora tres fichas aportadas como PDF,
rectificación separada de renovación y condiciones de estado civil. Consulte
[alcance, observaciones pendientes y reconstrucción del índice de siete TXT](docs/ampliacion-dni-mayor.md)
y los [resultados deterministas](docs/resultado-pruebas-dni-mayor.md).
Las combinaciones no confirmadas requieren revisión documental; las simulaciones
no sustituyen la validación local con el recuperador real.

Las combinaciones de renovación y rectificación aplican un
[control determinista de alcance documental y de salida](docs/control-afirmaciones-combinadas-pr4.md):
las tasas y condiciones individuales no se convierten en obligaciones conjuntas.
Este control no constituye una verificación factual universal del resto de respuestas.

La [estabilización de viudez y las disposiciones generales de adultos](docs/estabilizacion-viudez-disposiciones-pr4.md)
añade reglas de plazo, seguimiento y advertencias a los tres TXT de adultos.
Esta actualización requiere reconstruir el índice de los siete documentos.
Las abstenciones por recuperación incompleta se identifican como `abstencion_documental`
y diagnostican las reglas faltantes; no equivalen a una respuesta factual verificada.

La [lectura exacta de reglas autorizadas](docs/recuperacion-exacta-reniec-pr4.md)
resuelve omisiones del top-k sin aumentar `k` ni responder desde TXT ausentes del índice.
Puede diagnosticarse el índice local con `python -m app.rag.inspect_rules` (sin OpenAI).
Las fuentes exactas se identifican como `recuperacion: exacta`, con `distancia: null`.


### Estado consolidado del PR #4 — 28/10/2026

Renovación y rectificación adultas, matrimonio, divorcio y viudez usan siete TXT
(43 fragmentos al reconstruir). La confirmación operativa del usuario del
27/10/2026 autoriza exclusivamente la sustitución de la certificación consular
de defunción por acta plurilingüe municipal legalizada por Prefectura para
cónyuge italiano fallecido en Italia. Es procedencia distinta de los PDF;
otras nacionalidades y países conservan sus reservas documentales.

La recuperación semántica y exacta comparten autorización e integridad por
archivo/regla: contenido completo vigente y metadata coherente. Una incidencia
observada no se rehabilita por otro resultado; se abstiene sin responder desde
TXT ausentes del índice. Los TXT se consultan solo para validar los bloques.

`verificacion: ok` significa que se superaron los controles disponibles, **no
certifica exactitud factual universal**. La API conserva sus campos y valores;
Gradio muestra esta aclaración. Las métricas conservan columnas y distinguen
las intenciones adultas, amarillo a azul y `abstencion_documental`.

Validación determinista actual: **601 aprobadas, 6 de integración excluidas**.
Los informes anteriores son históricos. Ver [causas, política de rechazo,
compatibilidad de métricas, límites e instrucciones Windows/Conda](docs/integridad-metricas-pr4.md).
El cambio de código no modifica TXT ni obliga a reconstruir un índice ya
sincronizado; inspeccionarlo con `python -m app.rag.inspect_rules`. Si está
obsoleto, reconstruirlo localmente antes de validar con OpenAI real.

### Presentación ciudadana del PR #4

Las respuestas controladas separan documentos, condiciones e incertidumbre del
lenguaje de auditoría. Las notas técnicas quedan en la trazabilidad. La plantilla
de viudez conserva las características fotográficas completas en un bloque
desplegable; las combinaciones mantienen sus restricciones de requisitos y pago.
No hay una reformulación LLM posterior al verificador. Para las respuestas
individuales, las instrucciones de claridad son una guía de estilo, no una
certificación factual. Ver [cambios, ejemplos y validación Windows/Conda](docs/claridad-conversacional-pr4.md).
Resultado actualizado: **622 pruebas aprobadas y 6 de integración excluidas**.
No cambia el corpus ni es necesario reconstruir FAISS por esta mejora.
