# V1 — DNI amarillo a azul y fluidez acotada

Base estable: `9b6f85a`, conservada en `fix/dni-classification-context`. Rama de trabajo: `feature/v1-dni-amarillo-azul`, creada directamente desde esa base con el árbol limpio. No se modifica `main`, no se trabaja sobre V2 y no se crea ni fusiona un PR.

## Análisis previo y límites de la intervención

| Componente de respuesta | Implementación previa | Mejora localizada |
| --- | --- | --- |
| Aclaraciones, fuera de alcance, abstenciones y aviso de contexto | Textos deterministas en `redactar_respuesta` | Reconocer información parcial y dificultades, manteniendo la pregunta canónica pendiente. |
| Requisitos, tasas, fotos, citas y plazos con evidencia | `LLMService` usando fuentes filtradas, intención e historial limitado | Instrucciones breves de pertinencia y distinción del nuevo procedimiento. No se añade un clasificador LLM. |
| Domicilio sin procedimiento confirmado | Operación pendiente; formulación repetitiva | Reconocer el domicilio y seguir preguntando por la operación, sin equipararlo a renovación. |
| Incidencias de citas | Dependían de la redacción documental general | Respuestas deterministas acotadas, sin diagnosticar causas, plazas o fechas. |
| Cambio amarillo a azul | No estaba en el catálogo y podía confundirse con primera inscripción | Nueva operación en la misma política canónica y documento específico. |

Las aclaraciones se pueden mejorar sin cambiar lo que decide el sistema. En cambio, tasa, fotografías, URL y alcance del nuevo procedimiento requieren el TXT autorizado. Una explicación oficial de los errores de reservas o un límite de 15 días requeriría documentación vigente: **esa regla no aparece en ninguno de los cuatro TXT y no se incorpora**.

## A. Incorporación del procedimiento

### Fuente autorizada

El TXT no estaba inicialmente en el entorno. Se solicitó al usuario y se incorporó el adjunto como `data/raw/dni_amarillo_a_azul_primera_vez.txt`, sin recrear ni editar su contenido. Comparación byte a byte con el adjunto correcta.

SHA-256 del documento incorporado:

`43114eea43be48820e49ba2fc24c4d6feca5ae8ad522005f63a0965976b7e1a0`

Contiene €7, dos fotografías de 35 x 43 mm y sus características completas, así como la URL:

https://bookeo.com/cturin?type=223Y6PNNP174468CBDCD&option_TYPE_OF_SERVICE=YJUTCFLT

El alcance documentado es el cambio amarillo a azul al cumplir 17 años. No se afirma elegibilidad legal ni se crean procedimientos adicionales. Las respuestas deben mantener ese alcance, incluso cuando se solicita información por el nombre del trámite sin comunicar una edad. La edad sola no activa el cambio de color. No se almacena una edad exacta adicional.

### Clasificación y continuidad

- Operación interna `amarillo_a_azul`; intención `dni_amarillo_a_azul_primera_vez`.
- `evidencia_color` distingue la referencia al color de «primera inscripción» y procesa la negación del nuevo cambio.
- «DNI azul» o «azul por primera vez» sin contexto suficiente abre una aclaración `tipo_dni`. No selecciona arbitrariamente el corpus de €5 o €7.
- Si ya existe contexto confirmado del cambio, una repregunta «¿cuánto cuesta el DNI azul por primera vez?» conserva ese trámite.
- Responder que tiene amarillo puede completar la aclaración de tipo de DNI, pero no rehabilita un cambio que haya rechazado.
- Tener amarillo no selecciona por sí solo renovación ni cambio a azul. En una aclaración sobre azul, «es su primer DNI» sigue siendo ambiguo hasta precisar primera inscripción real o cambiar inequívocamente de procedimiento.
- Se conservan los rechazos, el cambio de titular, las dudas materiales y los mecanismos canónicos existentes.

Solo se añaden tres indicadores transitorios a `EvidenciaTurno`: referencia azul, posesión de amarillo y ausencia previa de DNI. No son una memoria alternativa ni nuevos campos personales del contexto persistido. Las nuevas operaciones y aclaraciones se guardan en las estructuras canónicas ya existentes.

### Selección documental explícita

`DOCUMENTOS_POR_INTENCION` es el catálogo único:

| Intención | Archivo permitido |
| --- | --- |
| `dni_menor_primera_vez` | `dni_menor_primera_vez.txt` |
| `dni_menor_renovacion` | `dni_menor_renovacion.txt` |
| `dni_consulta_estado` | `dni_consulta_estado.txt` |
| `dni_amarillo_a_azul_primera_vez` | `dni_amarillo_a_azul_primera_vez.txt` |

El filtro compara el nombre completo de `metadata.archivo`. Se eliminan las coincidencias parciales como `primera_vez`, que aceptarían los dos procedimientos. Las fuentes devueltas conservan el archivo/chunk realmente utilizado. Si los resultados no contienen el archivo autorizado, se vacían las fuentes y se abstiene sin llamar al generador.

No cambia el algoritmo FAISS, el splitter, la creación de embeddings ni el número de resultados solicitado. Tampoco se ha reconstruido el índice en desarrollo.

Se añade únicamente la URL exacta nueva a `OFFICIAL_URLS`, tras revisar el TXT recibido. Es una ampliación de datos de confianza para conservar literalmente el contacto aprobado, sin comodines ni cambios en las reglas de privacidad. Los enlaces anteriores permanecen intactos; no se altera autenticación ni autorización.

## B. Fluidez conversacional

`conversation_style.py` es un módulo de formulación, no un motor de decisión. No escribe estado ni autoriza fuentes.

- Domicilio: reconoce la nueva información y pregunta por la dimensión pendiente. No afirma que actualizar domicilio sea renovación. El extractor tampoco trata «actualizar DNI» como renovación cuando el objeto expresado es domicilio. Si ya existe trámite confirmado pero su fuente no explica domicilio, se abstiene de dar requisitos para ese cambio.
- Acceso al enlace: reconoce la dificultad, sin volver a ofrecer simplemente el mismo enlace ni atribuir una causa.
- Error de reservas: no lo identifica automáticamente con agenda completa.
- Sin citas: reconoce lo informado, pero no anuncia aperturas ni disponibilidad futura.
- Urgencia: orienta a consultar el sistema oficial sin prometer anticipación o reserva.
- Incidencia sin trámite identificado: reconoce la dificultad y pide el contexto necesario, sin RAG.

Las respuestas sobre incidencias con trámite confirmado se producen después de la elegibilidad canónica y recuperación de sus fuentes. La formulación determinista evita llamadas adicionales al LLM. Las respuestas documentales ordinarias siguen usando el proveedor existente.

El prompt añade instrucciones de proporción —costo, fotos y plazo sin listas ajenas al tema— y prohíbe al redactor reclasificar el procedimiento. Se corrige la generalización «ya tuvo DNI equivale a renovación» para que no absorba el cambio amarillo a azul. El historial no se convierte en fuente oficial. No se modifica el verificador factual.

## Archivos y funciones modificados

| Grupo | Archivo | Funciones/datos |
| --- | --- | --- |
| A | `data/raw/dni_amarillo_a_azul_primera_vez.txt` | Adjunto íntegro recibido. |
| A/B | `app/graph/classification.py` | `solicitante` —categoría al cumplir años—, nueva `evidencia_color`, `extraer_evidencia`; cautela con actualización de domicilio. |
| A | `app/graph/context_policy.py` | Catálogo y operación nueva; `validar_contexto`, `tramite_candidato`, `transicionar` para `tipo_dni`. La elegibilidad continúa en `ruta_documental`. |
| A | `app/graph/state.py` | Tres etiquetas transitorias de `EvidenciaTurno`; sin memoria paralela. |
| A | `app/graph/dni_graph.py` | `enriquecer_busqueda`, `recuperar_documentos`, aclaración nueva y excepción documental del prompt. |
| A | `app/core/official_contacts.py` | Una URL aprobada añadida, procedente del TXT. |
| B | `app/graph/conversation_style.py` | `menciona_domicilio`, `formular_aclaracion`, `tipo_incidencia`, `respuesta_contextual`. |
| B | `app/graph/dni_graph.py` | `redactar_respuesta`: formulación determinista localizada y párrafo de pertinencia del prompt. |
| A/B | `tests/test_v1_extension.py` | Clasificación, fuentes, conversación, abstención, URL, API y aislamiento. |
| A/B | Documentación y README | Matriz, validación sintética y actualización local. |

## Matriz de regresiones y resultado real

| Cobertura | Resultado |
| --- | --- |
| Cuatro solicitudes explícitas amarillo/azul, incluida edad 17 | Aprobado |
| Azul ambiguo, primer DNI ambiguo y aclaración posterior | Aprobado, sin RAG antes de resolver |
| Edad sola y tenencia de amarillo sin solicitud suficiente | No activan automáticamente el cambio |
| Repreguntas costo, fotos, cita y plazo | Fuente única del nuevo TXT; URL íntegra |
| Primera inscripción y renovación de menor | €5 y URL anterior, sin fuente de €7 |
| Documento nuevo ausente entre los resultados | Abstención; no sustituye con otra fuente |
| Negación, rectificación y observaciones después de rechazo | Rechazos conservados; sin rehabilitación por posesión |
| Cambio de procedimiento/titular | Fuentes del nuevo contexto o abstención adulta |
| Sesión nueva, borrado y API | Sin herencia; credencial y contrato conservados |
| Domicilio parcial y no documentado | Reconocimiento sin inferir operación ni requisitos |
| Cuatro incidencias y una incidencia inicial sin trámite | Respuesta contextual; sin causas, regla de 15 días ni fechas inventadas |
| Seguridad, privacidad, memoria y concurrencia V1 | Regresiones históricas conservadas |

Ejecución final: **327 aprobadas, 6 de integración excluidas, 12 advertencias de dependencias, 8,17 s**, Linux/Python 3.11.17.

Las 295 pruebas históricas se conservan sin editar expectativas. Se añaden 31 casos dirigidos; la parametrización histórica de contactos aprobados incorpora además la URL nueva, de ahí el incremento total de 32 casos. Los tests utilizan los cuatro TXT reales, recuperación simulada y un proveedor determinista de prueba. Las verificaciones de €5/€7 y URLs comprueban selección, contenido y flujo; **no equivalen a validar la comprensión o el texto de un LLM real**.

```bash
GRADIO_ANALYTICS_ENABLED=False XDG_CACHE_HOME=/tmp/tfm-cache PYTHONDONTWRITEBYTECODE=1 \
  env -u OPENAI_API_KEY -u TFM_OPENAI_API_KEY \
  .venv/bin/python -B -m pytest -q --tb=short -p no:cacheprovider
```

Comparación AST: verificador factual, historial y construcción del grafo idénticos a V1. Comparación Git: API, servicios, sesiones/TTL/borrado, Gradio, privacidad, concurrencia, n8n, dependencias, FAISS y los tres TXT anteriores intactos. La única modificación de datos de seguridad es la URL exacta aprobada descrita arriba. `git diff --check` correcto. No se han usado OpenAI real ni evaluaciones con conversaciones reales.

## Windows/Conda: actualización e índice

1. Detener la aplicación. Conservar una copia local del índice V1 y de su entorno fuera de los cambios que se publican. No versionar índices ni `.env`.
2. Actualizar la rama nueva, sin fusionarla con V1:

```powershell
git fetch origin
git switch feature/v1-dni-amarillo-azul
git pull --ff-only origin feature/v1-dni-amarillo-azul
conda activate tfm-piloto
python --version
```

3. Confirmar Python 3.11 y revisar los cuatro TXT. La nueva tasa debe ser €7 y la nueva URL debe terminar exactamente en `YJUTCFLT`; los dos trámites de menor mantienen €5 y `YMRKCTKN`.
4. Ejecutar la suite sin integración:

```powershell
$env:GRADIO_ANALYTICS_ENABLED = "False"
$env:PYTHONDONTWRITEBYTECODE = "1"
python -B -m pytest -q --tb=short -p no:cacheprovider
```

5. Solo después de verificar el corpus, reconstruir el índice usando las credenciales ya administradas localmente. **Este comando sí utiliza OpenAI para embeddings; no fue ejecutado por Codex:**

```powershell
python -c "from app.rag.index_builder import crear_indice_faiss; print(crear_indice_faiss())"
```

Se genera `data/vector_store/faiss_index`, excluido por `.gitignore`. No publicar el índice, claves ni resultados reales. Un índice antiguo no contiene el nuevo documento: el filtro seguro no lo sustituirá por el archivo de menor, pero hay que reconstruirlo para disponer de la nueva información.

6. Reiniciar mediante `python -m app.ui`, conservando el arranque seguro existente. No se necesitan nuevas dependencias ni variables. Las sesiones son efímeras y el reinicio pierde el contexto como en V1.

**Comparación/reversión:** cambiar de rama no cambia automáticamente el índice ignorado por Git. Para probar V1 `9b6f85a`, usar una copia de trabajo separada con su índice V1, o restaurar/reconstruir el índice de tres documentos antes de arrancar V1. No probar el filtro parcial de V1 con el índice nuevo de cuatro documentos: produciría una comparación incorrecta y podría mezclar las dos fuentes `primera_vez`.

## Conversaciones sintéticas para Gradio

Cada fila se inicia con «Nueva conversación». Son casos preparados para validación manual posterior; no fueron ejecutados aquí en Gradio/Windows ni con OpenAI real.

| Caso | Turnos sintéticos | Qué revisar |
| --- | --- | --- |
| A1 | «Mi hijo cumple 17 años y necesita cambiar su DNI amarillo por el azul» → «¿Cuánto cuesta?» → «¿Y las fotografías?» → «¿Dónde solicito la cita?» | €7, fotos de 35 x 43 mm y demás características del TXT; URL `YJUTCFLT`; solo archivo nuevo. |
| A2 | «Mi hijo menor necesita su primer DNI» → costo → cita | €5 y URL `YMRKCTKN`; sin contaminación del archivo azul. |
| A3 | «Necesito renovar el DNI de mi hijo menor» → costo → «Ahora quiero cambiar mi DNI amarillo a azul» | Cambio explícito; pasar de €5 a €7 con la fuente correspondiente. |
| A4 | «¿Cuánto cuesta el DNI azul por primera vez?» → «Ya tengo el amarillo» | Aclarar primero, conservar la consulta de coste y no asumir primera inscripción. |
| A5 | Cambio amarillo/azul → «No quiero cambiar el DNI amarillo a azul» → «Ya tiene el DNI amarillo» → solicitud explícita de cambio | No reactivar por una observación; permitir aceptación explícita posterior. |
| B1 | «Buenos días, necesito tramitar el DNI de mi hijo menor» → «Debo actualizar el domicilio» | Reconocer el dato y pedir operación, sin requisitos ni equivalencia automática con renovación. |
| B2 | Renovación confirmada → «El enlace de citas no funciona» → «La página de reservas da error» → «No aparecen citas disponibles» → «Necesito una cita lo antes posible» | Reconocer cada dificultad, sin repetir simplemente el enlace ni atribuir causas, plazas o regla de 15 días. |
| B3 | Amarillo/azul confirmado → «Ahora quiero renovar mi DNI, soy adulto» | Nuevo titular y abstención del procedimiento adulto no documentado. |
| S1 | Dos perfiles de navegador independientes; uno confirma amarillo/azul y el otro pregunta costo de azul sin contexto | El segundo debe aclarar; «Nueva conversación» tampoco hereda el trámite anterior. |

## Riesgos y límites pendientes

- El TXT recibido contiene una incoherencia editorial: en «ALCANCE» dice que no se añadieron plazos, pero después incorpora una sección de entrega de 3–4 meses. Se conserva íntegro y se señala para revisión documental; no se ha verificado vigencia normativa en línea. La respuesta real sobre plazo requiere especial comprobación manual.
- El nuevo documento se incorpora como recurso aprobado para el piloto, no como certificación de elegibilidad individual. Las respuestas deben limitarse al supuesto de cumplir 17 años con DNI amarillo.
- La naturalidad y el cumplimiento del prompt requieren validación lingüística real. Los mocks no la sustituyen; el verificador factual existente sigue teniendo sus limitaciones.
- La búsqueda semántica real puede no devolver suficientes fragmentos del archivo esperado dentro de los resultados. Se abstiene antes que utilizar otra fuente; no se ha evaluado aquí el índice reconstruido.
- Las reglas lingüísticas continúan siendo acotadas. No se añade un motor alternativo ni se intenta resolver casos extremos ajenos a esta ampliación.
- No se ejecutó Windows nativo, reconstrucción FAISS, proveedor real ni automatización n8n. V2 queda fuera del trabajo.

Preparado para revisión y validación local tras verificar el corpus y reconstruir el índice. No se fusiona ni se crea un PR de fusión.
