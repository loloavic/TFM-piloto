# Recuperación y cierre: cambio de renovación a estado civil — PR #4

Fecha: 29/10/2026. Base: ac1eebb. Rama: feature/dni-mayor-ampliacion. No se modifica main, no se fusiona el PR ni se cambia su estado.

## Recuperación del trabajo

Se recuperaron los cambios locales de la ejecución interrumpida. Antes de editar se comprobaron rama y HEAD, `git status --short`, diff de los cuatro módulos modificados y el archivo nuevo de dos reproducciones. No se descartó ningún cambio. HEAD y la rama remota actualizada seguían en ac1eebb.

Las dos pruebas que habían fallado contra la implementación anterior se ejecutaron primero tras recuperar los cambios y dieron **2 aprobadas**. No se atribuye resultado al proceso de pytest perdido en la desconexión: no pudo recuperarse su salida. La primera suite completa de esta recuperación dio **5 fallos y 784 aprobadas**; los cambios recuperados necesitaban acotación para conservar domicilio de menores y la aceptación de una derivación pendiente. Se corrigieron sin modificar ni retirar pruebas anteriores.

## Causas confirmadas

- `extraer_evidencia()` reconocía rectificar/corregir, pero no siempre convertía la acción actualizar estado civil en una operación explícita de rectificación.
- La transición suprimía una rectificación posterior a renovación salvo que apareciera un marcador de cambio como ahora. Por ello una petición independiente con pero necesito quedaba vinculada a la renovación anterior.
- La extracción de estado civil reconocía expresiones completas de casado a divorciado o respuestas aisladas, pero no el destino a divorciado dentro de esta solicitud. La actualización adulta de una renovación con estado civil retornaba sin pedir aclaraciones, y el plan de renovación con más de 60 días seguía devolviendo la explicación de no elegibilidad.
- Una pregunta pendiente de coste del objetivo anterior también podía conservar su prioridad al iniciar otro procedimiento.

El defecto no era de FAISS: la selección documental seguía la operación equivocada antes de recuperar fuentes.

## Cambios mínimos por archivo

| Archivo / funciones | Corrección |
|---|---|
| `app/graph/classification.py` / extraer_evidencia | Reconoce actualizar/cambiar estado civil como rectificación afirmativa, tras tratar las negaciones. Distingue una petición independiente de una adicional o simultánea; una aclaración nominal como sería un renuevo conserva su interpretación previa |
| `app/graph/state.py` / EvidenciaTurno | Añade objetivo_independiente como booleano transitorio. No guarda nuevas identidades, texto ni datos personales en el estado canónico |
| `app/graph/context_policy.py` / transicionar | Cuando existe otra operación y llega un nuevo objetivo independiente, aplica cambio de operación y retira el tema pendiente anterior. No convierte en nuevo objetivo la respuesta que acepta una derivación documental pendiente. Las peticiones adicionales conservan el control de combinación |
| `app/graph/adult_context.py` / extraer | Reconoce el destino solicitado a casado/divorciado/viudo, sin afirmar un estado matrimonial anterior. Un destino explícito no se reemplaza por una referencia histórica como me casé en Perú. Destinos incompatibles quedan en contradicción |
| `app/graph/adult_context.py` / actualizar | El rechazo de renovación no bloquea una consulta civil independiente mediante la derivación propia de rectificación de datos. El cambio reutiliza la conservación de vigencia del mismo titular y el reinicio de condiciones ajenas al nuevo objetivo |
| `tests/test_operation_goal_change.py` | 21 regresiones nuevas de conversaciones completas; incluye las dos reproducciones recuperadas |
| README y este informe | Recuperación, evidencia, alcance y pasos Windows/Conda |

No se cambia el plan documental, `dni_graph.py`, los controles de salida, RuleIntegrity, las tarifas ni el umbral. Se elimina la causa del enrutamiento incorrecto; no se omiten las comprobaciones de autorización ni se fuerza una fuente civil desde el redactor. No cambian los siete TXT, el índice de aplicación ni los contratos de API.

## Comportamiento y aclaraciones

Secuencia de referencia:

1. Mi DNI vence dentro de 61 días. ¿Puedo renovarlo ahora? → pide edad.
2. Mayor de edad → explica que todavía no corresponde renovación.
3. Pero necesito actualizar mi estado civil a divorciado → cambia la operación canónica a rectificacion, mantiene titular, edad y mas_60 y elimina el propósito anterior de elegibilidad. Pregunta **solo si desea recuperar el apellido materno**.
4. No quiero recuperar el apellido materno → fuentes autorizadas `dni_mayor_estado_civil.txt`, reglas general y divorcio. Si desea recuperarlo, añade apellido y conserva su documentación específica.

Durante una aclaración material la intención pública puede ser general y las fuentes estar vacías, conforme a la puerta canónica existente. Esto no significa seguir en renovación: la operación y condiciones internas ya son civiles. Se recuperan los documentos cuando se completa la información necesaria, no antes.

No se almacena un supuesto de estado matrimonial previo. Se identifica el destino solicitado y se usan las condiciones de la regla oficial correspondiente, sin inventar actas adicionales. Las pruebas inspeccionan que el contexto entregado al generador contiene el acta matrimonial con anotación de disolución y el acta de nacimiento solo cuando procede recuperar el apellido; no certifican todas las salidas posibles de un LLM real.

| Situación | Resultado |
|---|---|
| Renovación a 61/90 días → solicitud civil independiente | Rectificación civil, con vigencia anterior conservada y preguntas documentales propias |
| Renovación a 61 días → necesito rectificar fecha de nacimiento | Rectificación individual de datos, sin fuente de renovación |
| DNI vencido → solicitud civil independiente | No implica combinación automática con renovación, aunque su vigencia permita renovar |
| A 59 días → renovación con rectificación / también rectificar | Se conserva la combinación de datos autorizada y su regla de no acumulación |
| Renovación con estado civil expresamente conjunta | Continúa sin autorización para requisitos conjuntos; abstención |
| Estado civil → puedo renovar mi DNI ahora | Nueva consulta independiente de renovación, conservando la vigencia y retirando condiciones civiles ajenas |
| Sería un renuevo durante una aclaración civil | No se borra el contexto por interpretarlo arbitrariamente como otro objetivo |
| Cambio de titular | Se invalidan vigencia y condiciones del anterior mediante la política existente |

## Resultados ejecutados

**808 aprobadas, 6 de integración excluidas, 12 advertencias de dependencias, 11,88 s**, Python 3.11/Linux. Se conservan las 787 pruebas anteriores sin modificar sus expectativas y se añaden 21.

Cobertura nueva: reproducción de divorcio después de renovación no procedente; renovación a 90 días y destino casado; lugar del matrimonio; rectificación de fecha; combinación autorizada a 59 días y petición adicional; vencido con cambio civil independiente, con/sin rechazo de renovación; apellido sí/no y repreguntas de requisitos/coste/cita; nueva consulta de renovación; coste anterior; otro titular, documento de tercero y sesión independiente; fuentes civiles ausente/incompleta/obsoleta/contradictoria; matrimonio histórico frente a destino solicitado; destinos contradictorios; combinación civil no autorizada y aclaración de coste pendiente de otro objetivo.

Las fuentes inválidas no reutilizan las reglas de renovación ni producen una afirmación aparentemente verificada. No se utilizó OpenAI real ni se reconstruyó/modificó FAISS de producción. Los proveedores de generación son simulados y las pruebas FAISS existentes usan índices temporales/vectores artificiales. No se instalaron dependencias ni se modificaron credenciales.

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

No reconstruir FAISS por esta entrega. Usar el índice ya sincronizado de siete TXT y 44 fragmentos. La inspección opcional `python -m app.rag.inspect_rules`, sin --consulta, no consume embeddings. Reiniciar el servidor y probar la secuencia original en una sesión nueva; después responder sobre el apellido y consultar documentos/coste/cita. Verificar fuentes civiles exclusivas y conservación de mas_60. Probar también renovación con rectificación a 59 días, rechazo de renovación y cambio de titular.

## Riesgos residuales y validación pendiente

El reconocimiento de solicitudes independientes y aditivas es determinista y lingüísticamente acotado; no garantiza resolver todas las ambigüedades. La combinación civil permanece restringida y el importe exacto conjunto de renovación con rectificación de datos no se inventa. La verificación fuera de los ámbitos controlados conserva sus límites: ok no certifica fidelidad factual universal.

Queda pendiente repetir la conversación en Windows/Conda con Gradio y el proveedor real. Los resultados de esta entrega no se presentan como validación nativa en Windows ni comprobación normativa externa. El estado canónico, seguridad, privacidad, aislamiento y retención siguen conservando sus controles existentes.
