# Responder primero a la elegibilidad — PR #4

Fecha: 29/10/2026. Base: 20a6cb6. Rama: feature/dni-mayor-ampliacion. No se modifica main ni se fusiona o cambia el estado del PR.

## Causa confirmada

`renovacion_adulta()` trataba el tema otra como petición general de coste y documentos. Con vigencia confirmada hasta_60/vencido no añadía una decisión inicial: la primera frase era la tasa. La rama mas_60 sí explicaba la decisión, pero no empezaba por una negativa directa. Con umbral desconocido se limitaba a explicar la regla y enumerar información.

El clasificador y la política ya distinguían correctamente las consultas originales. Por eso no se modifican. La mejora es únicamente de presentación: reconocer si el ciudadano pregunta por poder renovar y ordenar la información según esa pregunta.

## Cambios por archivo y función

- `app/graph/presentation.py`: `consulta_elegibilidad()` reconoce expresiones de presentación como puedo renovar/renovarlo y me corresponde. No determina edad, operación, vigencia ni autorización. `renovacion_adulta()` usa la vigencia canónica, ya validada, para abrir con sí, no o una aclaración. Suprime coste/fotografías/cita no solicitados en una pregunta puramente de elegibilidad, pero conserva información completa cuando se pide explícitamente. No confunde «mi documento» con una petición de lista de documentos.
- `app/graph/combination_guard.py`: pasa el historial existente al formateador. Solo se usa para retomar nuestra aclaración de vigencia ante una respuesta sobre vencimiento, preservando solicitudes complementarias de coste/documentos. El historial no aporta requisitos ni decide la elegibilidad: la decisión sigue dependiendo de la categoría canónica y de la regla autorizada.
- `tests/test_renewal_eligibility_presentation.py`: 26 casos nuevos; ninguna prueba anterior modificada.
- README y este informe: evidencia, alcance y validación Windows.

No se modifica `dni_graph.py`: redactor y verificador ya llaman a la misma respuesta controlada. Ambos recalculan el texto final con los mismos datos; no existe reformulación posterior por LLM. Las comprobaciones previas de autorización, completitud y RuleIntegrity permanecen intactas.

## Antes y después

| Situación | Antes | Ahora |
|---|---|---|
| 59 o 60 días, pregunta si puede renovar | Tasa €7, fotografías y cita sin decisión inicial | «Sí, puede renovar su DNI ahora. La renovación corresponde cuando el DNI está vencido o le quedan 60 días o menos de vigencia» |
| 61 días | Explicación del umbral | «No, todavía no corresponde renovar su DNI. El DNI conserva más de 60 días de vigencia. Podrá renovarlo cuando le queden 60 días o menos, o si ya está vencido» |
| Vencido y pregunta si puede renovar | Información general sin afirmación inicial | Sí, sin volver a pedir fecha |
| Vigencia desconocida y pregunta de elegibilidad | Condición general, tasa y documentos | «¿El DNI está vencido, vence dentro de 60 días o menos, o le quedan más de 60 días? No indique la fecha exacta» |
| Requisitos o coste expresos | Información individual | Se conserva documentación completa o importe individual; si también pregunta por elegibilidad, la decisión aparece primero |

La aclaración de presentación no añade un nuevo pendiente canónico ni cambia los contratos. Al contestar con la vigencia, se usa su extracción y estado actuales y se retoma la pregunta de elegibilidad; una repregunta posterior sobre coste deja de repetir el sí innecesariamente.

## Pruebas y garantías

Antes de implementar: **4 pruebas fallidas**, correspondientes a 59/60/61 y vigencia desconocida.

Suite final: **743 aprobadas, 6 de integración excluidas, 12 advertencias de dependencias, 10,51 s**. Python 3.11/Linux. Se conservan las 717 anteriores y se añaden 26.

Cobertura nueva: primera afirmación de 59/60/61; vencido; puedo renovarlo/me corresponde/ya puedo renovar mi documento; desconocido; requisitos y coste solos; preguntas mixtas; continuación tras aclaración y cambio de tema; negación y titular menor; ausencia, obsolescencia, contradicción y archivo no autorizado; verificador ante borrador afirmativo cuando no corresponde renovar. Se comprueban también las condiciones fotográficas completas y el enlace cuando se piden documentos.

Los casos inválidos se abstienen sin fuentes ni afirmación aparentemente verificada. La pregunta puramente de elegibilidad no llama al LLM ni agrega tasas o requisitos. Los controles de combinaciones/no acumulación, las fuentes y los mecanismos de seguridad siguen cubiertos por la suite anterior.

No se utilizó OpenAI real, no se reconstruyó FAISS y no se ejecutó Windows nativo.

## Limitación previa identificada, fuera de este cambio

La formulación inicial «Soy adulto y mi DNI vence dentro de 59 días. ¿Puedo renovarlo ahora y qué requisitos debo presentar?» puede activar la aclaración de edad del clasificador existente por su tratamiento de presentar/documentos de apoyo. No se resuelve en esta entrega porque se ha prohibido modificar clasificación y titular. Se verifica la petición conjunta equivalente con «puedo renovar mi DNI» y la petición pronominal en una sesión con titular adulto ya establecido. Esta limitación no afecta a los tres casos de referencia, pero debe tenerse presente en validación real; no se afirma cobertura universal de expresiones mixtas.

La interpretación del historial para retomar la aclaración es acotada a sus turnos recientes y a esa pregunta determinista. No es una nueva memoria de identidad ni una fuente normativa. Persisten los límites lingüísticos y factuales previos; `ok` significa superar los controles disponibles, no exactitud universal.

## Actualización y Windows / Conda

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

**No reconstruir FAISS por esta entrega.** Los siete TXT y el índice sincronizado de 44 fragmentos no cambian. La inspección opcional `python -m app.rag.inspect_rules`, sin --consulta, no utiliza OpenAI. No modificar credenciales ni .env.

En conversaciones nuevas, repetir exactamente los tres casos de referencia. Verificar primera frase afirmativa en 59/60 y negativa en 61, fuente general exclusiva y ausencia de fotografías/tasa no solicitadas. Probar vencido y desconocido → respuesta con vigencia → coste; después requisitos, consulta conjunta, negación y cambio a menor. La conversación real con proveedor y la evaluación visual en Windows quedan pendientes.
