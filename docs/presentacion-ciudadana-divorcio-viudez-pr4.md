# Presentación ciudadana de divorcio y viudez — PR #4

Fecha: 29/10/2026. Base: 3bf1c0f. Rama: feature/dni-mayor-ampliacion. No se modifica main, no se fusiona el PR ni se cambia su estado.

## Diagnóstico y alcance

Los formatos anteriores reproducían bloques completos autorizados. Eso conservaba hechos, pero trasladaba al ciudadano instrucciones de edición/control: no exigir por inferencia, no confundir matrimonio/defunción y referencias vagas a condiciones generales. Las formalidades peruanas estaban en una sección distinta del acta; el motivo del registro consular aparecía aunque no se hubiera preguntado.

La intervención es únicamente de presentación para divorcio y viudez de cónyuge italiano fallecido en Italia. Clasificación, contexto canónico, transiciones, planes, recuperación semántica/exacta y datos opcionales no se modifican. Los otros supuestos conservan sus reservas y formatos prudentes; no se extrapola la sustitución italiana.

## Archivos y funciones

- `app/graph/presentation.py`: `_datos_civiles_ciudadanos` extrae tasa, fotografías, cita y formalidades de la regla general ya autorizada. `divorcio_ciudadano` y `viudez_italiana_ciudadana` construyen apartados separados desde los fragmentos autorizados. `_apellido_ciudadano` mantiene la condición explícita y su ámbito peruano. `_condiciones_ciudadanas` reúne tasa individual, características fotográficas completas y cita, sin duplicar el bloque global de formalidades.
- `app/graph/combination_guard.py`: usa estos formatos únicamente en las ramas ya autorizadas de divorcio y viudez italiana. Si no pueden interpretarse las condiciones esperadas, devuelve MISSING y conserva la abstención, sin delegar una reescritura al LLM. El verificador existente recompone la misma salida final.
- `tests/test_civil_citizen_format.py`: 28 regresiones nuevas.
- Tres archivos de pruebas anteriores (`test_citizen_presentation`, `test_optional_surname`, `test_widow_confirmation`): ajustes de expectativas de redacción (apostilladas → con apostilla), mayúsculas y nuevo título de sección. Se conservan todos los casos y sus comprobaciones de hechos/fuentes; no se eliminan tests ni se relajan autorizaciones.
- README, este informe y comparativa completa: evidencia e instrucciones.

No se modifican TXT, FAISS, API, seguridad, privacidad, sesiones, tarifas, no acumulación ni umbral de 60 días. No hay proveedor, agente, modelo o dependencia nuevos.

## Presentación y fidelidad documental

Los formatos interpretan estructuras conocidas de las reglas, no inventan texto normativo a partir de la pregunta. Extraen el número de meses y la tasa del contenido autorizado; comprueban que el documento remite expresamente a las condiciones peruanas antes de presentarlas. Una forma no interpretable se abstiene en vez de completar un vacío.

| Apartado | Información conservada / ámbito |
|---|---|
| Divorcio, acta matrimonial | Acta de matrimonio peruana original con anotación de disolución del divorcio. Apostilla del Ministerio de Relaciones Exteriores, emisión máxima de 12 meses y buen estado junto al acta |
| Defunción italiana | Acta plurilingüe municipal legalizada por Prefectura competente, exclusivamente cónyuge italiano fallecido en Italia. No requiere certificación consular adicional, porque esa acta la sustituye |
| Matrimonio registrado en Perú | Acta matrimonial peruana original con formalidades peruanas explícitas |
| Matrimonio registrado en oficina consular peruana | Copia certificada de esa oficina. No se le atribuyen apostilla ni 12 meses por analogía |
| Apellido, solo si se necesita / solicitud expresa | Acta de nacimiento original. Formalidades peruanas únicamente si fue emitida en Perú. Una negativa excluye el apartado conforme al plan existente |
| Condiciones generales | Tasa individual €7, fotografías sin inventar cantidad, características completas desplegables y enlace oficial íntegro. Reserva de combinación con renovación conservada en lenguaje sencillo |

Las alternativas de matrimonio se expresan como **si está registrado en…**, no como dos documentos simultáneamente obligatorios. La defunción y el matrimonio tienen apartados distintos. El acta de nacimiento nunca está en la lista principal universal.

Las formalidades se muestran una vez por documento afectado: matrimonio peruano y, cuando figura, nacimiento emitido en Perú. Esa repetición breve mantiene ambos ámbitos explícitos y evita remisiones vagas; se elimina su tercera aparición genérica en condiciones generales. No se repiten fotografías, tasa ni cita. No se presentan condiciones peruanas en el apartado italiano ni en la alternativa consular.

La explicación sobre registro consular solo puede añadirse cuando se pregunta explícitamente por su motivo, dentro de una consulta correctamente enrutada. Se elimina de la orientación documental ordinaria. Las frases dirigidas al sistema no se muestran; los textos originales permanecen intactos en corpus, contexto y trazabilidad.

No se añaden formalidades de documentos extranjeros ni se afirma que estén exentos: las fuentes no desarrollan todos esos supuestos. Tampoco se certifica vigencia normativa externa. La denominación Prefectura conserva la autoridad que figura en el TXT; no se añade otra legalización.

## Comparación completa

La [comparativa antes/después](comparativa-presentacion-civil-pr4.md) contiene las cuatro respuestas completas, con fotografías y enlaces. Se generó ejecutando el código determinista de la versión base y el nuevo con los mismos fragmentos autorizados. No se presenta como salida observada de un proveedor real.

El antes contiene «Aplicar condiciones generales de documentos peruanos» y «No exigir… por inferencia». El después muestra directamente cada documento y sus formalidades, la sustitución italiana y el apellido condicional, sin instrucciones de control.

## Pruebas ejecutadas

Antes de modificar producción: **3 pruebas fallidas**, dos por instrucciones técnicas filtradas y una por ausencia de formalidades junto al acta principal.

Suite final: **867 aprobadas, 6 de integración excluidas, 12 advertencias de dependencias, 12,72 s**, Python 3.11/Linux. Se conservan los 839 casos anteriores y se añaden 28.

Las pruebas nuevas verifican decisiones desconocida/sí/no sobre apellido, documentos principales y opcionales separados, ámbitos por apartado, alternativas de registro matrimonial, no duplicación de tasa/fotografías/cita, formalidades junto al acta, enlaces íntegros, ausencia de instrucciones técnicas, fuentes ausente/incompleta/obsoleta/contradictoria, salida final frente a borradores que universalizan apostilla o acta de nacimiento, abstención si el formateador no interpreta la fuente, explicación de registro solo cuando se pide, continuidad renovación → divorcio, aislamiento y conservación de renovación/rectificación de datos.

No se utilizó OpenAI real ni se alteró el índice de aplicación. La suite conserva FAISS temporal con vectores artificiales y las regresiones de seguridad, privacidad y concurrencia. No se realizaron instalaciones ni cambios de credenciales.

## Windows / Conda

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

No reconstruir FAISS por esta entrega: los siete TXT y 44 fragmentos siguen intactos. Usar el índice sincronizado de la fase anterior. Inspección opcional sin OpenAI: `python -m app.rag.inspect_rules` (sin --consulta). Reiniciar la interfaz y abrir sesiones nuevas.

Validar las dos consultas de referencia y sus variantes de apellido desconocido/sí/no. Comprobar visualmente apartados, fotografías desplegables, enlaces completos y formalidades locales. Repetir 61 días → divorcio independiente, matrimonios registrados en Perú/oficina consular, renovación y rectificación de datos, y nueva sesión. Usar datos ficticios. No se ha repetido aquí la validación Windows/Gradio con el proveedor real aportada para la versión base.

## Riesgos residuales

Los formatos están vinculados a estructuras conocidas de fuentes autorizadas: una actualización futura de redacción puede requerir adaptar el extractor, y se abstiene si no puede interpretarla con seguridad. La clasificación de preguntas ambiguas conserva sus límites anteriores; no se modifica para ampliar consultas de otros servicios civiles. Las reglas de otros países/nacionalidades no se completan por analogía.

Fuera de estos formatos controlados permanece el alcance limitado del verificador. `ok` no certifica exactitud factual universal. La claridad y accesibilidad visual deben comprobarse en la instalación local antes de la defensa; la prueba HTTP no sustituye una revisión humana de la interfaz.
