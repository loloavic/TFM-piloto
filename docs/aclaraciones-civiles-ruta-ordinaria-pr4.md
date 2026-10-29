# Aclaraciones civiles y ruta ordinaria — PR #4

Fecha: 29/10/2026. Base: `4d733c4`. Rama: `feature/dni-mayor-ampliacion`.

## Diagnóstico confirmado

No bastaba con cambiar una pregunta de lugar. `transicionar()` añadía edad pendiente a toda rectificación sin edad conocida; `adult_context.actualizar()` retornaba antes de preparar las preguntas civiles si la edad no era adulta confirmada. Finalmente `ruta_documental()` rechazaba las operaciones sin edad confirmada. Además, `solicitante()` reconocía el objeto propio «actualizar mi estado civil ... DNI» pero no lo trasladaba al indicador de titular propio cuando no había una expresión contigua «mi DNI» o una edad explícita.

Se añadieron y ejecutaron siete reproducciones antes de modificar producción: **7 fallidas**. Las siete pasan después. No se modificaron las 900 pruebas anteriores.

## Política aplicada y archivos

- `app/graph/adult_context.py`: `ruta_civil_ordinaria()` distingue selección de ficha de declaración de edad. Es una política derivada del contexto canónico, no un dato demográfico persistido. Solo acepta ámbito DNI, titular propio confirmado, rectificación confirmada no rechazada, modificación civil confirmada y edad desconocida sin contradicción. Rechaza dudas de titular, documento, operación, procedimiento previo o contradicciones. `actualizar()` prepara las aclaraciones civiles en ese supuesto y elimina únicamente la falta rutinaria de edad; no elimina contradicciones de edad. Sin transición conocida, exige la transición incluso si se pregunta por otro tema.
- `app/graph/context_policy.py`: candidato y autorización admiten la ruta civil ordinaria explícita. La autorización sigue exigiendo contexto válido y ausencia de pendientes materiales. El seguimiento conserva la ficha civil autorizada. No se habilitan renovación, datos personales ni otros procedimientos por esta excepción.
- `app/graph/classification.py`: reconoce el titular propio en la solicitud explícita de actualización de **mi estado civil** vinculada al DNI. La traza interna añade `ruta_ordinaria:estado_civil_sin_edad_declarada`; la proyección del solicitante sigue indicando grupo desconocido, no adulto. La etiqueta histórica `dni_adulto_rectificacion` describe la ficha seleccionada, no confirma una edad.
- `app/graph/conversation_style.py`: formulación ciudadana de la pregunta por transición; mantiene el saludo final existente.
- `tests/test_civil_ordinary_route.py`: 25 casos nuevos multivuelta y parametrizados.

No cambian el esquema canónico, los contratos API, el detector social, el verificador ni la generación documental determinista. No se usa la ley matrimonial como evidencia de edad, ni se incorporan nuevas reglas legales al corpus.

| Situación | Actuación |
|---|---|
| Propio DNI, cambio civil sin transición ni edad | Preguntar qué cambio civil necesita; edad permanece desconocida |
| Transición a matrimonio | Preguntar lugar del matrimonio si falta |
| Transición a viudez | Preguntar lugar de fallecimiento y nacionalidad cuando corresponde |
| Divorcio ordinario identificado | Ficha civil autorizada; apellido materno continúa opcional |
| Menor declarado | No aplicar excepción ni reglas adultas; abstención/flujo existente |
| Edad contradictoria | Mantener bloqueo hasta nueva evidencia suficiente |
| Titular tercero de edad desconocida | Mantener aclaración de edad; no extender excepción |
| Cambio posterior a renovación | Volver a exigir edad si sigue desconocida |
| Documento ausente, alterado o contradictorio | Conservar abstención documental |
| Saludo puro | Camino social sin proveedores ni cambios de contexto |

## Ejemplos completos antes/después

Entrada: «Buenas noches, quiero actualizar mi estado civil en el DNI».

Antes:

> ¡Buenas noches!
>
> Para poder orientarle, Indique si el titular del DNI es menor de 18 años o adulto.

Después:

> ¡Buenas noches!
>
> Con gusto puedo orientarle sobre la actualización de su estado civil en el DNI.
>
> ¿Qué cambio necesita realizar: de soltero a casado, de casado a divorciado o de casado a viudo?

Entrada siguiente: «de soltero a casado».

Antes: «Para poder orientarle, Indique si el titular del DNI es menor de 18 años o adulto.»

Después: «Para poder orientarle, ¿El matrimonio se celebró en Perú o fuera de Perú?»

Son reproducciones deterministas con proveedores simulados, no nuevas validaciones reales con OpenAI. «a divorciado» permite continuar con la presentación documental existente; «a viuda» solicita primero el dato de fallecimiento que falte. No se infiere el estado matrimonial anterior como hecho independiente.

## Evidencias y límites

Las pruebas comprueban edad vacía/desconocida en el snapshot incluso después de recuperar fuentes; solo se permiten reglas de `dni_mayor_estado_civil.txt`. Se verifican aclaraciones sucesivas, repreguntas de coste, cita, plazo, requisitos y seguimiento, fuentes inválidas, edad contradictoria, matrimonio histórico con menor explícito, matrimonio extranjero, nuevo titular y sesión independiente. Las 900 regresiones previas incluyen saludos, integridad, seguridad, privacidad y concurrencia.

La orientación ordinaria no certifica elegibilidad personal ni mayoría de edad. En terceros, casos históricos sin información clara o expresiones no reconocidas puede ser necesaria una aclaración prudente. Una edad menor explícita nunca se transforma en adulta por una referencia matrimonial. El reconocimiento lingüístico conserva sus límites; las pruebas no demuestran cobertura universal.

## Validación Windows / Conda

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

Repetir la introducción civil, responder con cada transición en sesiones nuevas y verificar que se solicita solo la circunstancia documental pendiente. Probar después renovación para confirmar que vuelve a solicitarse edad; probar menor explícito y otra sesión. No reconstruir FAISS: no cambia el corpus. No editar credenciales. Windows nativo y OpenAI real quedan pendientes de validación local.

## Resultado ejecutado

Linux, Python 3.11.17, `.venv` existente. Comando:

```bash
GRADIO_ANALYTICS_ENABLED=False XDG_CACHE_HOME=/tmp/tfm-cache PYTHONDONTWRITEBYTECODE=1 env -u OPENAI_API_KEY -u TFM_OPENAI_API_KEY .venv/bin/python -B -m pytest -q --tb=short -p no:cacheprovider
```

Resultado final: **925 passed, 6 deselected, 12 warnings in 13.95s** (900 anteriores + 25 nuevas). Las seis de integración real quedan excluidas por la configuración existente. No se usó OpenAI real; los proveedores de los casos nuevos son simulados. `git diff --check` sin errores; comparación del corpus con `4d733c4` vacía. No se modificó el índice local de producción.
