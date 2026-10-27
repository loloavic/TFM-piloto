# Confirmación operativa de viudez — PR #4

Fecha: 27 de octubre de 2026. Rama: feature/dni-mayor-ampliacion.

## Alcance y procedencia

El usuario responsable del piloto confirma exclusivamente la sustitución de la certificación consular de defunción por el acta de defunción plurilingüe municipal italiana, legalizada por la Prefectura competente, cuando el cónyuge era italiano y falleció en Italia. Es confirmación operativa del usuario, separada del PDF original y de una comprobación normativa en línea (no realizada). Se registra en la cabecera del TXT. La denominación aprobada es «plurilingüe»: no se normaliza «integral» como equivalente.

Se conserva la acreditación del matrimonio según su registro, independiente de la defunción. La respuesta presenta las alternativas condicionales, sin dar por confirmado el lugar de inscripción del matrimonio ni exigir las dos actas de matrimonio. Apellido materno conserva su regla independiente. No se amplía la sustitución a peruanos, otras nacionalidades, nacionalidad desconocida u otros países. En esos escenarios se mantienen reservas documentales; no se declara confirmado un listado por la mera mención de inscripción consular.

## Causa y cambios

Las reglas viudez_italia e italiano mantenían la incertidumbre sobre acumulación/sustitución y activaban la salida determinista de observación pendiente. Dos regresiones (con/sin recuperación de apellido) fallaron antes de cambiar la implementación.

- `data/raw/dni_mayor_estado_civil.txt`: procedencia diferenciada, regla italiana con sustitución explícita, matrimonio independiente y reserva para nacionalidades no cubiertas. Los otros seis TXT no cambian.
- `app/graph/combination_guard.py`: caso cerrado para viudez italiana en Italia y tema requisitos/otra. Valida plan, completitud, fuentes y duplicados antes de emitir textos autorizados. Omite solamente la reserva destinada a otros supuestos; si no encuentra la estructura esperada, se abstiene. El verificador reutiliza el mismo control y reemplaza borradores divergentes: no depende de una recomendación al LLM. Tarifas/cita y disposiciones comunes mantienen sus controles anteriores.
- `app/graph/adult_context.py`: una regresión nueva reveló que la extracción codiciosa de lugar de defunción podía capturar «Perú» de una oración posterior sobre matrimonio. Se acota a la oración y al primer lugar de la cláusula de defunción. No se infiere nacionalidad ni lugar de registro por este cambio.
- Tests: nuevo `test_widow_confirmation.py` (13 casos); expectativas históricas de observación actualizadas solo para el supuesto ahora confirmado en tres archivos. Ningún test anterior eliminado.

## Validación

Suite determinista completa en Python 3.11/Linux: **573 aprobadas, 6 de integración excluidas, 12 advertencias de dependencias**. Incluye 560 casos existentes y 13 nuevos. Proveedores simulados; algunos tests existentes emplean FAISS temporal real con vectores artificiales. No se utilizó OpenAI real ni se validó Windows nativo ni se reconstruyó el índice de despliegue.

Nuevos casos: sustitución con/sin apellido; requisitos y repreguntas de coste/cita/plazo/seguimiento; nacionalidad desconocida y corregida; otro país; matrimonio registrado en Perú u oficina consular; peruano con inscripción consular sin extrapolación; verificador ante borrador deliberadamente incorrecto.

## Windows / Conda

```powershell
git fetch origin
git switch feature/dni-mayor-ampliacion
git pull --ff-only origin feature/dni-mayor-ampliacion
conda activate tfm-piloto
$env:GRADIO_ANALYTICS_ENABLED="False"
$env:PYTHONDONTWRITEBYTECODE="1"
python -B -m pytest -q --tb=short -p no:cacheprovider
```

Detener el servidor y respaldar el directorio del índice configurado antes de reemplazarlo. El cambio del corpus exige reconstrucción con las credenciales locales ya configuradas; no copiarlas ni registrarlas. La siguiente operación sí usa el proveedor real de embeddings y debe ejecutarse localmente:

```powershell
python -c "from app.rag.index_builder import crear_indice_faiss; print(crear_indice_faiss())"
python -m app.rag.inspect_rules
python -m app.ui
```

Comprobar siete fuentes, reglas completas y coincidencia con TXT actuales (se mantienen los 43 fragmentos). Reiniciar el servidor para usar el nuevo índice. Repetir conversación en sesión nueva: viudez, Italia, cónyuge italiano y respuesta sobre apellido; luego requisitos/coste/cita/plazo/seguimiento. Corregir a «no era italiano» y comprobar reserva sin sustitución. No reutilizar un índice antiguo: la recuperación exacta rechaza bloques distintos del TXT, pero la búsqueda semántica no constituye una certificación general de vigencia del índice.

Linux usa los mismos comandos Python tras activar su entorno; las variables se establecen con `export`.

## Límites

No se afirma validación oficial en línea. El extractor sigue siendo lingüístico y no cubre todas las redacciones. Los procedimientos individuales no cubiertos por controles deterministas conservan el generador y verificador existentes; no se garantiza fundamentación universal. La reserva para otros escenarios y las alternativas de matrimonio son deliberadas. Seguridad, privacidad, sesiones, endpoints, prompts, dependencias y main permanecen intactos. PR #4 no se fusiona.
