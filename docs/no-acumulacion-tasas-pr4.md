# No acumulación de tasas — PR #4

Fecha: 29/10/2026. Base: 06b8313. Rama: feature/dni-mayor-ampliacion. No se modifica main ni se fusiona el PR; no se cambia su estado de borrador.

## Confirmación y límites

El usuario responsable del conocimiento operativo consular confirma expresamente que las tasas de renovación y rectificación de DNI no son acumulables cuando ambas operaciones se realizan conjuntamente. En este piloto se aplica a la combinación ya autorizada de renovación y rectificación de datos de adultos. Se registra como confirmación operativa del 29/10/2026, separada de los PDF y sin afirmar verificación normativa externa.

Esto permite afirmar **no acumulación**, no deducir una tarifa conjunta nueva. Los importes individuales documentados siguen siendo €7. No se afirma un importe conjunto de €14 ni una tasa única conjunta de €7 ni una exoneración. Falta una confirmación expresa del Consulado sobre el importe exacto aplicable al caso conjunto y su alcance; esa es la aclaración adicional necesaria, no una nueva lista de documentos.

Se mantiene la procedencia de renovación por DNI vencido o hasta 60 días restantes. No se extiende la regla a estado civil, menores, amarillo a azul u otras combinaciones. Con más de 60 días, rectificación individual no pasa a renovación. Vigencia desconocida en una solicitud de renovación con rectificación mantiene la aclaración previa.

## Causa anterior y cambio

El corpus y la plantilla anteriores reflejaban que solo se conocían los importes individuales; por ello explicaban que no estaba confirmado si se acumulaban. La nueva confirmación resuelve esa parte, pero no el importe conjunto exacto. El plan anterior no exigía una fuente específica para la política tarifaria.

| Archivo | Cambio y justificación |
|---|---|
| `data/raw/dni_mayor_renovacion.txt` | Procedencia tarifaria diferenciada y una única regla completa `no_acumulacion`, añadida al final para conservar los chunk existentes |
| `data/raw/dni_mayor_rectificacion.txt` | Sustituye la reserva antigua sobre acumulación por referencia a la política específica; registra procedencia, sin duplicar el bloque normativo |
| `app/graph/adult_context.py` | Plan no común de combinación autorizada exige general + no_acumulacion de renovación; no añade esa regla a procedimientos individuales ni disposiciones comunes |
| `app/graph/combination_guard.py` | Exige el bloque tarifario, conserva tasas individuales y documentos, elimina la incertidumbre resuelta y presenta la no acumulación sin inventar importe conjunto. La regla tarifaria no se enumera como documento de rectificación |
| `app/graph/classification.py` | Reconoce pagar/pagan/abonar y tasas en plural como coste para preguntas de pago y repreguntas breves |
| `tests/test_joint_tariff.py` | 23 casos nuevos; proveedores simulados y FAISS temporal con vectores artificiales cuando corresponde |
| Dos archivos de pruebas anteriores | Inventario actualizado de 43 a 44 fragmentos; expectativas sobre dos tasas sustituidas por la afirmación confirmada de no acumulación, conservando sus demás comprobaciones |
| README, guía principal, informe de vigencia y este informe | Estado actual, procedencia y reconstrucción; la evidencia histórica de vigencia se conserva identificada |

Los otros cinco TXT no cambian. No se modifica RuleIntegrity ni su autorización/validación compartida. La regla nueva es evidencia indexada obligatoria, no conocimiento de respaldo leído desde TXT. Si falta, está incompleta, obsoleta o contradicha, se elimina la evidencia parcial y se abstiene; no se responde la política desde una constante. La lectura exacta de respaldo solo rescata un bloque autorizado que realmente existe en el índice y coincide con el corpus.

El verificador sigue recalculando la respuesta controlada final. Un borrador que acumule tasas, fije €14 o declare tasa conjunta de €7/exoneración es sustituido y observado. La no determinación del importe exacto se comunica al ciudadano; `ok` sigue significando únicamente que se superaron los controles disponibles.

## Antes / después

Antes: «No puedo confirmar el importe total ni si las tasas se acumulan para este supuesto».

Ahora: «La rectificación cuesta €7 y la renovación €7, cada una para su procedimiento individual. No puedo confirmar el importe total del caso conjunto. […] Las tasas de renovación y rectificación de datos del DNI de adulto no son acumulables cuando ambas operaciones se realizan conjuntamente. No debe sumar las dos tasas individuales. […] Confirme con el Consulado qué importe corresponde pagar para su caso conjunto».

En una consulta conjunta de coste y requisitos se mantienen además la partida de nacimiento original apostillada, antigüedad máxima de 12 meses, alternativa consular de copia certificada y la reserva sobre antigüedad de esa copia. No se convierten en una tarifa conjunta ni se añaden documentos.

## Pruebas ejecutadas

Reproducción previa: **4 pruebas nuevas fallidas**, por falta de afirmación explícita y de la regla obligatoria en el plan.

Resultado final: **681 aprobadas, 6 de integración excluidas, 12 advertencias, 10,48 s**, Linux/Python 3.11. Se conservan los 658 casos previos y se añaden 23. Las actualizaciones de expectativas anteriores son consecuencia de la confirmación nueva y del fragmento añadido, sin retirar casos ni controles de seguridad.

Cobertura nueva: DNI vencido, 59/60/61 días; renovación con rectificación; coste y requisitos; preguntas de 7 o 14 euros; tasas en plural y varios turnos; vigencia desconocida; fuentes ausente/incompleta/obsoleta/contradictoria; verificador contra acumulación, tarifa conjunta no confirmada y exoneración; no extensión a otros procedimientos; respaldo exacto autorizado con FAISS real temporal; índice anterior sin política que se abstiene aunque el TXT actual exista.

No se utilizó OpenAI real ni se reconstruyó o modificó el índice de aplicación. No hay dependencias nuevas, cambios de credenciales, API, métricas, sesiones, privacidad ni infraestructura.

## Windows / Conda y reconstrucción obligatoria

El corpus sigue teniendo siete TXT, pero ahora **44 fragmentos** por la nueva regla. La inspección existente descubre automáticamente la regla añadida y compara su vigencia contra el TXT; no necesita otra lista manual. No basta con que el índice anterior tenga las dos reglas generales.

Detener el servidor y respaldar el directorio del índice configurado antes de reconstruir. Usar las credenciales locales existentes sin publicarlas ni modificar .env.

```powershell
git fetch origin
git switch feature/dni-mayor-ampliacion
git pull --ff-only origin feature/dni-mayor-ampliacion
conda activate tfm-piloto
$env:GRADIO_ANALYTICS_ENABLED="False"
$env:PYTHONDONTWRITEBYTECODE="1"
python -B -m pytest -q --tb=short -p no:cacheprovider
python -c "from app.rag.index_builder import crear_indice_faiss; print(crear_indice_faiss())"
python -m app.rag.inspect_rules
python -m app.ui
```

La reconstrucción sí consume embeddings reales; no se ejecutó aquí. La inspección sin --consulta no utiliza OpenAI. Comprobar 44 fragmentos y coincidencia de todas las reglas, incluida `dni_mayor_renovacion.txt#no_acumulacion`; reiniciar la aplicación. Linux usa los mismos comandos Python tras activar su entorno, con variables mediante export.

Validación real pendiente: Gradio con DNI vencido y a 59/60/61 días; preguntar requisitos y coste a la vez, «¿debo pagar 7 o 14 euros?» y «¿y las tasas?» en la misma sesión. Comprobar que no propone acumulación ni una tarifa conjunta exacta, conserva fuentes/documentos y no traslada la regla a menores o estado civil. Windows nativo y proveedor real no se validaron en esta ejecución.

## Riesgos residuales

El importe exacto del caso conjunto sigue pendiente de confirmación y no debe inferirse del hecho de no acumular. La procedencia es operativa del usuario, no normativa externa. Subsisten límites lingüísticos y del verificador fuera de los ámbitos deterministas. El índice debe mantenerse sincronizado y como artefacto confiable local; los diagnósticos de integridad no sustituyen esa disciplina de despliegue.
