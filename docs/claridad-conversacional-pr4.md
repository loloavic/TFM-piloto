# Claridad y fidelidad conversacional — PR #4

Fecha: 28/10/2026. Base: 16bb883. Rama: feature/dni-mayor-ampliacion.

## Diagnóstico de las rutas de respuesta

| Ruta | Problema anterior | Cambio / garantía |
|---|---|---|
| Combinaciones deterministas | Nombres TXT y reglas, citas técnicas, reservas repetidas | Etiquetas de procedimiento y documentos individuales; conserva los límites de combinación |
| Viudez italiana confirmada | Reproducción íntegra de general y observaciones de edición del PDF | Documentos primero, condiciones después; características fotográficas completas en bloque desplegable |
| Viudez no confirmada | OBSERVACIÓN PENDIENTE y lista ambigua de certificados | Incertidumbre sobre qué certificado corresponde, con remisión al Consulado y condiciones confirmadas separadas |
| Generación LLM individual | El contexto incluye anotaciones técnicas que el modelo puede repetir | Instrucciones de estilo para pregunta actual, listas útiles y lenguaje ciudadano, sin segundo modelo ni reformulación posterior |
| Aclaraciones | Preguntas guiadas por motivo pendiente | Se conservan; no se modifica la clasificación ni se inventan nuevas preguntas |
| Ausencia / integridad fallida | Corpus, índice y reglas en el texto ciudadano | Explica que no puede confirmar la información y remite al Consulado; causa técnica sigue en verificacion/estado |
| Plazo, seguimiento y advertencias | Reglas comunes completas | Se conservan sus hechos y alcance determinista, sin añadir requisitos de viudez |
| Fuera de alcance / procedimiento no documentado | Referencias a fuentes cargadas y corpus | Alcance del asistente y remisión directa a canales oficiales |

## Implementación

- `app/graph/presentation.py`: sustituciones explícitas de notas editoriales conocidas; plantillas para requisitos de viudez y reservas de defunción. No es un resumen libre, no extrae obligaciones de la pregunta y no usa otro LLM.
- `app/graph/combination_guard.py`: mantiene autorización, completitud y control de combinaciones. Compone la presentación final antes de devolverla; el verificador vuelve a calcular exactamente esa misma salida. La viudez incierta queda cubierta también por la comparación determinista, sin convertir actas alternativas en exigencias acumulativas.
- `app/graph/dni_graph.py`: redacción de abstenciones/fuera de alcance, instrucciones de estilo del LLM y clasificación de incertidumbre material como abstencion_documental. La reserva contenida en viudez_italia para otras nacionalidades no marca como incierto el caso italiano ya confirmado. Los borradores sustituidos por el control siguen observados.
- `tests/test_citizen_presentation.py`: 21 casos nuevos. Cinco archivos de pruebas existentes actualizan únicamente expectativas de texto que cambió intencionadamente; se conservan sus controles funcionales, fuentes y aislamiento.
- README y este informe: resultados, comparaciones, validación y límites.

No cambian los siete TXT, FAISS, clasificación, catálogo, sesiones, privacidad, endpoints, dependencias ni modelos. Tampoco se transforma la respuesta después del verificador. El historial guarda la misma salida final que recibe el ciudadano.

## Ejemplos antes / después

Extractos; las condiciones completas permanecen en las respuestas correspondientes.

| Antes | Después |
|---|---|
| «La ficha PDF específica no indica cantidad de fotos; el plazo común se registra por separado» | «Confirme con el Consulado la cantidad de fotografías que debe llevar»; el detalle fotográfico obligatorio permanece accesible |
| «Ficha de rectificación (dni_mayor_rectificacion.txt, regla datos) — cita…» | «Rectificación — documentación individual: Para rectificar… partida de nacimiento original apostillada con antigüedad no mayor a 12 meses…» |
| «La ficha aportada contiene una observación documental pendiente» | «No puedo confirmar todavía qué documento de defunción debe presentar… ni si el acta original y la certificación consular se sustituyen o deben presentarse juntas. Confirme este punto con el Consulado antes de acudir» |
| «Es necesario revisar el corpus o el índice» | «Consulte con el Consulado antes de acudir; no debe utilizar los requisitos de otro trámite» |
| «La ficha de rectificación indica €7 y la de renovación €7» | «La rectificación cuesta €7 y la renovación €7, cada una para su procedimiento individual. No puedo confirmar el importe total ni si las tasas se acumulan…» |

La respuesta de viudez ordena defunción, matrimonio y apellido cuando procede. Conserva la sustitución únicamente para cónyuge italiano fallecido en Italia, condiciones de documentos peruanos, alternativas de registro matrimonial y enlace de cita completo. No traslada la regla italiana a la respuesta de otra nacionalidad: esa regla no está autorizada en su plan.

## Fidelidad y trazabilidad

La respuesta restringida se construye antes de la verificación final, que recalcula la plantilla y rechaza cualquier borrador distinto. No se añade una segunda reformulación que pueda cambiar tasas o requisitos después del control. La recuperación continúa usando RuleIntegrity y plan canónico; una regla obsoleta, contradictoria o ausente conserva su abstención y no genera una respuesta afirmativa.

Las observaciones originales permanecen en contexto/fragmentos y documentos internos, no en el texto ciudadano. La incertidumbre material sobre viudez recibe `abstencion_documental: condiciones parcialmente no confirmadas`; es un valor dentro de la familia existente, no un nuevo campo de API. Métricas conserva la categoría abstencion_documental. Los consumidores que comparen literalmente el detalle, en lugar del prefijo, deben tenerlo en cuenta.

El texto de respuesta ya admite formato Markdown. Se incorpora HTML estándar `<details>` únicamente para las características fotográficas en la plantilla de viudez. El contenido completo se entrega en la misma cadena de API y Gradio; no se elimina ni se exige otra consulta para obtenerlo. Un consumidor que no renderice HTML puede mostrarlo como texto; revisar la presentación antes de la defensa. Las pruebas HTTP confirman conservación del contenido, no el aspecto final en el navegador Windows.

## Pruebas ejecutadas

Antes de cambiar producción: los cuatro casos iniciales nuevos fallaron (viudez confirmada, incierta, requisitos combinados y abstención).

Resultado final: **622 aprobadas, 6 de integración excluidas, 12 advertencias de dependencias, 9,37 s**, en Linux/Python 3.11. Se conservan los 601 casos anteriores y se añaden 21. No se utilizó OpenAI real ni se alteró el índice de aplicación.

Además de la ausencia de términos técnicos, se comprueban: acta plurilingüe, autoridad municipal/Prefectura, sustitución condicional, no exigencia de certificación consular italiana, matrimonio según registro, apellido, apostilla/antigüedad, características completas y enlace; plazo referencial, RENIEC al 100 % sin disponibilidad automática; temas e historial; instrucciones a generación individual de adulto, menor, amarillo a azul y rectificación; control final frente a importes/fotografías inventados; reglas faltantes, contradictorias y obsoletas; reserva y trazabilidad de casos inciertos; conservación del contenido en API/Gradio.

## Windows / Conda

```powershell
git fetch origin
git switch feature/dni-mayor-ampliacion
git pull --ff-only origin feature/dni-mayor-ampliacion
conda activate tfm-piloto
$env:GRADIO_ANALYTICS_ENABLED="False"
$env:PYTHONDONTWRITEBYTECODE="1"
python -B -m pytest -q --tb=short -p no:cacheprovider
python -m app.rag.inspect_rules
python -m app.ui
```

No reconstruir FAISS por este cambio: el corpus no cambia. Usar el índice ya sincronizado de siete TXT/43 fragmentos. No cambiar .env ni credenciales.

Validación real pendiente: revisar visualmente el desplegable fotográfico y los enlaces completos; preguntar requisitos → coste → cita → plazo → seguimiento → recomendaciones en una sesión de viudez; repetir con nacionalidad no italiana y verificar reserva; cambiar a menor; comprobar renovación adulta, amarillo a azul y rectificación. Usar datos ficticios. Esta validación sí usa el proveedor configurado y no se ejecutó aquí.

## Límites

Las plantillas deterministas tienen comparación final verificable. Las instrucciones al LLM mejoran el estilo, pero no garantizan obediencia universal ni ausencia de errores factuales en todos los procedimientos individuales. No se presenta `ok` como certificación factual universal. Tampoco se afirma una evaluación humana de naturalidad o accesibilidad de navegador ya realizada. Subsisten límites lingüísticos previos y reservas documentales; no se amplía el catálogo ni se resuelven supuestos administrativos no confirmados.
