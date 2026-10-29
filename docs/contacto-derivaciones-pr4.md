# Contacto consular en derivaciones — PR #4

Fecha: 29/10/2026. Base: `5638322`. Rama: `feature/dni-mayor-ampliacion`.

## Causa y procedencia

Las respuestas de abstención y confirmación consular indicaban acudir a canales oficiales sin facilitar un contacto concreto. No era un error de clasificación ni de integridad documental. El caso de la hija de 16 años se reprodujo con una prueba **fallida antes del cambio**: la abstención era correcta, pero faltaba el correo. La misma prueba pasa después.

El responsable del proyecto confirma `informes@conperturin.org` como contacto operativo. La dirección ya pertenecía a `app/core/official_contacts.py`, lista controlada por código: no es necesario modificarla ni ampliar las excepciones de privacidad. La confirmación es de contacto, no una autorización de requisitos o procedimientos.

## Cambios por archivo

- `app/graph/referral.py`: formateador puro `incorporar_contacto()`. Detecta formulaciones expresas de consulta, confirmación, comunicación o contacto con el Consulado/oficina consular. Añade un único bloque con dirección fija y enlace `mailto:`. No duplica una dirección ya presente, incluso en mayúsculas. No consulta proveedores ni procesa texto del ciudadano como autoridad de contacto. Excluye formulaciones negativas habituales y requiere que la dirección siga en la lista controlada.
- `app/graph/dni_graph.py`: llama al formateador **después** del cálculo completo de verificación y antes de guardar respuesta/historial. No altera el borrador documental previamente comprobado para obtener un dictamen distinto, ni vuelve a pedir una respuesta al LLM. Las fuentes, intención, estado canónico y resultado de verificación se conservan; solo cambia la presentación de la respuesta. El bloque fijo no contiene requisitos, importes ni plazos administrativos.
- `tests/test_consular_referral.py`: reproducciones y regresiones descritas abajo.
- `README.md` y este informe: resultado, alcance y guía local.

No cambian contratos públicos, estado de sesión, autorizaciones, reglas consulares, integridad, TXT, índice FAISS ni credenciales.

## Antes y después completos

Consulta: «Mi hija de 16 años necesita actualizar su estado civil en el DNI. ¿Qué documentos debe presentar?».

Antes:

> Identifico el trámite de DNI solicitado, pero no dispongo de información confirmada sobre sus requisitos, tarifas y condiciones. Por favor, consulte los canales oficiales del consulado.

Después:

> Identifico el trámite de DNI solicitado, pero no dispongo de información confirmada sobre sus requisitos, tarifas y condiciones. Por favor, consulte los canales oficiales del consulado.
>
> Para recibir orientación, puede escribir al Consulado General del Perú en Turín: [**informes@conperturin.org**](mailto:informes@conperturin.org).
>
> Le recomiendo explicar brevemente el trámite que desea realizar para que la oficina consular pueda indicarle los requisitos correspondientes.

La intención sigue siendo `general`, sin fuentes, sin llamadas RAG/OpenAI. La verificación existente de este caso sigue siendo `ok`: no se convierte artificialmente en otra etiqueta. Las abstenciones documentales de reglas ausentes o contradictorias mantienen su etiqueta `abstencion_documental`; una salida previamente observada mantiene `observada`. El correo añadido no constituye una validación factual.

## Política y pruebas

Se comprueban menor explícito; fuentes ausentes y contradictorias; combinación no confirmada; derivación expresa con objeto intermedio; idempotencia y contactos ya presentes; mensajes negativos; respuesta completa sin derivación; Bookeo; RENIEC; saludo puro; continuidad y sesión independiente. Las pruebas de fallo documental ejecutan el mismo escenario con/sin formateador y comparan intención, fuentes, contexto canónico y verificación. Comprueban también que no se crean prompts LLM adicionales.

Una respuesta civil que sí recomienda confirmar fotografías/requisitos incorpora el contacto y conserva Bookeo. Una respuesta de citas que únicamente remite al sistema de reservas no lo incorpora. El seguimiento RENIEC ordinario y el saludo puro permanecen sin el bloque. El historial utiliza los mismos límites y minimización existentes; no se guarda ningún dato personal nuevo.

La primera suite ampliada detectó una formulación no cubierta («escribir al Consulado»); se añadió soporte para infinitivos con `al` y para confirmación de un punto intermedio. La suite final se ejecutó de nuevo tras esas correcciones y las pruebas de negación.

## Riesgos residuales

El detector es determinista y cubre las formulaciones de derivación existentes y las variantes probadas; no garantiza reconocer toda paráfrasis futura de un LLM. Las nuevas formulaciones deben tener regresiones. No corrige ni reinterpreta el dictamen factual original. El contacto no garantiza respuesta, disponibilidad de cita ni plazo de atención. No se comprueba entrega del correo ni se envía ningún mensaje. Si cambia el canal oficial, deben actualizarse por revisión la constante y la lista controlada; no procede aceptar contactos alternativos declarados por un usuario o generados por el LLM.

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

Repetir el caso de la menor, una consulta de reglas no disponibles, una cita ordinaria y un seguimiento. Comprobar enlace `mailto:`, ausencia de duplicación, Bookeo/RENIEC y trazas sin cambios. No reconstruir FAISS ni editar `.env`. Windows nativo y OpenAI real no se ejecutaron en esta intervención; requieren validación local.

## Resultado ejecutado

Linux, Python 3.11.17, entorno `.venv` existente, sin claves OpenAI en el proceso:

```bash
GRADIO_ANALYTICS_ENABLED=False XDG_CACHE_HOME=/tmp/tfm-cache PYTHONDONTWRITEBYTECODE=1 env -u OPENAI_API_KEY -u TFM_OPENAI_API_KEY .venv/bin/python -B -m pytest -q --tb=short -p no:cacheprovider
```

**958 passed, 6 deselected, 12 warnings in 14.35s**: 925 anteriores más 33 nuevas. Las seis de integración quedan excluidas por la configuración existente; no se ejecutaron. Los avisos son de dependencias. `git diff --check` sin errores y comparación del corpus con `5638322` vacía. Sin instalación de dependencias ni reconstrucción del índice.
