# Continuidad de elegibilidad y aclaración de edad — PR #4

Fecha: 29/10/2026. Base: b50e67f. Rama: feature/dni-mayor-ampliacion. No se modifica main, no se fusiona el PR ni se cambia su estado.

## Causas confirmadas

1. La pregunta «¿puedo renovarlo ahora?» quedaba clasificada con tema otra. La política conservaba el trámite y la vigencia, pero no distinguía ese propósito de una petición general. Después de «adulto», la presentación solo veía la aclaración actual; el recurso anterior al historial reconocía únicamente nuestra pregunta de vigencia, no una aclaración de edad, y dependía de turnos recientes.
2. `solicitante()` no reconocía mayor, para mayor de edad, el titular es mayor de edad o tiene más de 18 años como respuestas contextuales. Algunas formas reconocidas podían además interpretar el dato como un nuevo destinatario, en lugar de completar solo edad.
3. En consultas mixtas con edad explícita, DNI propio y renovarlo, la mención de presentar podía enmascarar al solicitante como apoyo documental. Esta limitación se había señalado en b50e67f; ahora el alcance autorizado incluye el reconocimiento del titular y se corrige de forma acotada.

Reproducción inicial antes de cambios productivos: **15 pruebas fallidas** de continuidad y variantes de edad. Antes de corregir el tercer punto se ejecutaron otras **2 pruebas fallidas** de consulta inicial mixta. No son resultados de OpenAI real.

## Modelo y correcciones por archivo

| Archivo / función | Cambio |
|---|---|
| `state.py`: ContextoCanonico / EvidenciaTurno | Añade consulta_renovacion como lista canónica / tupla de evidencia con categorías elegibilidad, coste, requisitos, fotografias, cita. No guarda pregunta, nombres, edad exacta ni fechas |
| `classification.py`: consulta_elegibilidad / componentes_elegibilidad | Detector único de propósito y componentes expresamente solicitados; reutilizado por presentación. No decide si procede renovar |
| `classification.py`: clasificar / extraer_evidencia / solicitante | Activa lectura contextual de edad solo con ámbito DNI validado, edad pendiente y sin ambigüedad pendiente de titular/documento. Respuestas completas permitidas completan edad sin sustituir el titular. No se admiten menciones de padre/acompañante/representante como confirmación |
| `classification.py`: solicitante | Reconoce renovación pronominal ligada a mi DNI, sin otro titular ni rol de apoyo y con operación afirmativa validada, para que presentar requisitos no borre la edad explícita |
| `context_policy.py`: contexto_inicial / validar_contexto / transicionar | Valida el vocabulario categórico y conserva propósito durante aclaraciones. Preguntas nuevas de tema distinto, rechazo de renovación, cambio de operación o reinicio/cambio de titular retiran el propósito que ya no corresponde |
| `presentation.py`: renovacion_adulta | Usa el propósito canónico para contestar primero elegibilidad y mantener únicamente coste/documentos/cita solicitados. Elimina la búsqueda del propósito en texto del historial |
| `combination_guard.py`: llamada al formateador | Deja de pasar el historial: la salida controlada se recompone desde contexto validado y reglas autorizadas |
| `tests/test_eligibility_context.py` | 44 casos nuevos de conversación completa y estado; no se modifican pruebas anteriores |
| README y este informe | Estado, ejemplos, compatibilidad y validación local |

El tema ordinario y la operación siguen separados del propósito. Esta intervención no añade una nueva intención, procedimiento ni fuente. La vigencia continúa en condiciones_adulto y se conserva al completar edad. El propósito no confirma edad, operación ni requisitos y nunca desbloquea por sí solo la recuperación documental.

## Ciclo del propósito y privacidad

- Una petición de elegibilidad guarda solo sus componentes categóricos dentro de la sesión y revisión actuales.
- Adulto / mayor contextual completa edad; no reemplaza la pregunta ni cambia el destinatario.
- La respuesta usa edad y vigencia canónicas, más la regla general recuperada y validada. La pregunta original puede desaparecer del historial limitado sin que se pierda el propósito.
- Una pregunta posterior de coste/requisitos cambia el foco y no repite la afirmación de elegibilidad innecesariamente.
- Negar renovación elimina su propósito activo y conserva el rechazo de operación. Cambiar de titular reinicia el contexto y descarta edad, vigencia y propósito anteriores.
- Un historial manipulado con importes o reglas falsas no cambia la respuesta controlada. No se lee como evidencia normativa ni como mecanismo de recuperación del propósito.

Las formas nuevas mayor, para mayor de edad y tiene más de 18 años no se interpretan como confirmaciones globales fuera de la aclaración autorizada. Las formas anteriormente admitidas conservan su comportamiento. Respuestas negativas o referencias a terceros no completan el dato pendiente. Si falta identificar un titular inequívoco, la ampliación contextual no cierra esa duda.

## Ejemplos antes / después

| Secuencia | Antes | Ahora |
|---|---|---|
| 59 días → adulto | Tasa, fotos y cita | «Sí, puede renovar su DNI ahora…» sin información no solicitada |
| 60 días → es adulto | Tasa y requisitos | Afirmación explícita, manteniendo hasta_60 |
| 61 días → mayor / para mayor de edad | Bucle de aclaración | «No, todavía no corresponde renovar su DNI…» manteniendo mas_60 |
| Vencido → adulta | Información general | Sí, sin pedir una fecha de vencimiento |
| Elegibilidad y coste → aclaración de edad | Se podía perder el primer propósito | Sí/no primero y tasa individual si fue solicitada |
| Elegibilidad y requisitos → aclaración de edad | Se podía perder la pregunta inicial | Sí/no primero, fotografías completas y cita cuando se piden documentos |

No se añaden tasas conjuntas ni se altera la regla de no acumulación. Los datos particulares de los documentos de rectificación y todas las condiciones de fuentes permanecen intactos.

## Pruebas ejecutadas

Suite final: **787 aprobadas, 6 de integración excluidas, 12 advertencias de dependencias, 11,40 s**, Python 3.11/Linux. Se conservan las 743 pruebas anteriores sin modificar sus expectativas y se añaden 44.

Casos nuevos: 59/60/61 y vencido; diez formas adultas; seis formas menores; negativas y menciones de terceros; expresiones nuevas sin contexto; edad y vigencia aclaradas en ambos órdenes; coste y requisitos posteriores; peticiones mixtas; edad explícita en consulta inicial mixta; cambio de titular y sesión independiente; ausencia/obsolescencia/contradicción documental; propósito validado sin texto libre; historial manipulado y pregunta original ya expulsada del historial limitado tras siete turnos.

Se comprueba primera afirmación, categoría de vigencia, edad, identidad del titular sin sustitución, pendientes vacíos al resolver, componentes del propósito, ausencia de importes/fotografías no solicitados y reglas/fuentes autorizadas. Las pruebas existentes siguen verificando seguridad, aislamiento, concurrencia, borrado, no acumulación y recuperación exacta.

No se utilizó OpenAI real ni se modificó el índice de aplicación. No se instalaron dependencias ni se modificaron credenciales.

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

No reconstruir FAISS por esta entrega: los siete TXT y 44 fragmentos no cambian. La inspección opcional `python -m app.rag.inspect_rules` sin --consulta no usa embeddings. No cambiar .env.

Reiniciar el servidor y abrir sesiones nuevas para probar cada secuencia 59 → adulto, 60 → es adulto, 61 → mayor y 61 → para mayor de edad. Repetir vencido, edad/vigencia en ambos órdenes, coste/requisitos después y cambio de titular. La memoria es efímera: no se reconstruye el propósito de conversaciones anteriores a esta versión leyendo texto histórico. La validación Windows nativa y conversación con el proveedor real quedan pendientes.

## Límites y compatibilidad

El campo nuevo es interno; no cambia el contrato FastAPI ni las categorías de métricas. Estados anteriores sin ese campo se admiten como propósito vacío; no se inventa retrospectivamente una intención. Los demás controles y la política de retención no cambian.

El vocabulario sigue siendo acotado y no resuelve toda expresión ambigua. Se prefieren preguntas guiadas cuando el titular o la edad no son inequívocos. No se afirma que ok certifique exactitud factual universal ni que una confirmación de propósito sustituya la autorización documental. Los casos de referencia están preparados para repetir validación real; no se declara esa validación ya realizada.
