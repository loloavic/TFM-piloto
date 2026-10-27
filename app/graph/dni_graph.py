import re
from app.core.privacy import minimizar_texto

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, StateGraph

from app.graph.state import DNIState
from app.graph.combination_guard import respuesta_controlada, COMMON_CONFLICT
from app.graph.classification import clasificar, pregunta_contextual
from app.graph.context_policy import DOCUMENTOS_POR_INTENCION, ruta_documental
from app.graph.adult_context import ADULT_FILES, PREGUNTAS as ADULT_PREGUNTAS, plan as plan_adulto
from app.graph.conversation_style import formular_aclaracion, respuesta_contextual
from app.rag.retriever import recuperar_contexto
from app.rag.exact_rules import recuperar_reglas_exactas
from app.services.llm_service import LLMService


# Número máximo de interacciones completas conservadas
# temporalmente dentro de cada sesión.
MAX_TURNOS_HISTORIAL = 6


def es_mensaje_sobre_contexto(
    pregunta_lower: str,
) -> bool:
    """
    Detecta expresiones mediante las cuales el ciudadano indica
    que ya proporcionó el contexto del trámite.
    """
    expresiones = [
        "ya le dije",
        "ya te dije",
        "ya indiqué",
        "ya indique",
        "ya lo indiqué",
        "ya lo indique",
        "ya mencioné",
        "ya mencione",
        "ya lo mencioné",
        "ya lo mencione",
        "ya expliqué",
        "ya explique",
        "ya lo expliqué",
        "ya lo explique",
        "de eso estamos hablando",
        "ese es el trámite",
        "ese es el tramite",
        "me refiero al mismo trámite",
        "me refiero al mismo tramite",
        "es el mismo trámite",
        "es el mismo tramite",
    ]

    return any(
        expresion in pregunta_lower
        for expresion in expresiones
    )


def clasificar_intencion(state: DNIState) -> DNIState:
    return clasificar(state)



def enriquecer_busqueda(
    state: DNIState,
) -> DNIState:
    """
    Construye una búsqueda RAG contextualizada.

    Añade el trámite identificado para evitar que una repregunta
    breve recupere documentos pertenecientes a otro procedimiento.
    """
    pregunta = pregunta_contextual(state)
    pregunta_lower = pregunta.lower()
    intencion = state.get(
        "intencion",
        "general",
    )

    palabras_costo = [
        "costo",
        "coste",
        "cuánto cuesta",
        "cuanto cuesta",
        "precio",
        "pago",
        "tasa",
        "monto",
        "importe",
    ]

    palabras_requisitos = [
        "requisito",
        "requisitos",
        "documento",
        "documentos",
        "qué llevar",
        "que llevar",
        "debo llevar",
        "debe llevar",
        "necesito llevar",
        "presentar",
    ]

    palabras_presencia = [
        "acompañado",
        "acompanado",
        "acompañada",
        "acompanada",
        "acompañar",
        "acompanar",
        "debe ir",
        "puede ir",
        "presente",
        "presencia",
        "padre",
        "madre",
        "hermano",
        "hermana",
        "apoderado",
        "representante",
    ]

    palabras_cita = [
        "cita",
        "reservar",
        "reserva",
        "enlace",
        "link",
        "bookeo",
        "turno",
        "turnos",
        "horario",
        "horarios",
        "atienden",
        "atención",
        "atencion",
        "por la mañana",
        "por la manana",
        "en la mañana",
        "en la manana",
        "por la tarde",
        "en la tarde",
        "en las tardes",
        "qué días",
        "que dias",
        "días disponibles",
        "dias disponibles",
        "fechas disponibles",
    ]

    palabras_plazo = [
        "cuánto demora",
        "cuanto demora",
        "cuánto tarda",
        "cuanto tarda",
        "tiempo de entrega",
        "plazo de entrega",
        "cuándo llega",
        "cuando llega",
        "cuándo estará listo",
        "cuando estara listo",
        "cuándo está listo",
        "cuando esta listo",
        "meses",
        "demora",
        "tarda",
    ]

    descripcion_intencion = {
        "dni_adulto_renovacion": "renovación de DNI de mayor de edad",
        "dni_adulto_rectificacion": "rectificación de DNI de mayor de edad",
        "dni_menor_renovacion": (
            "renovación de DNI de menor de edad"
        ),
        "dni_menor_primera_vez": (
            "DNI de menor de edad por primera vez"
        ),
        "dni_consulta_estado": (
            "consulta de estado del trámite de DNI "
            "en RENIEC"
        ),
        "dni_amarillo_a_azul_primera_vez": (
            "cambio de DNI amarillo a DNI azul por primera vez, supuesto documentado de cumplir 17 años"
        ),
    }

    partes_busqueda = [pregunta]
    if intencion in ADULT_FILES:
        partes_busqueda.append(str({key: d['valor'] for key, d in
            state['contexto_canonico'].get('condiciones_adulto', {}).items()}))

    if intencion in descripcion_intencion:
        partes_busqueda.append(
            "trámite relacionado: "
            f"{descripcion_intencion[intencion]}"
        )

    if any(
        palabra in pregunta_lower
        for palabra in palabras_costo
    ):
        partes_busqueda.append(
            "pago tasa consular costo precio "
            "monto euros importe del trámite"
        )

    if any(
        palabra in pregunta_lower
        for palabra in palabras_requisitos
    ):
        partes_busqueda.append(
            "requisitos y documentos necesarios"
        )

    if any(
        palabra in pregunta_lower
        for palabra in palabras_presencia
    ):
        partes_busqueda.append(
            "presencia del menor padre madre "
            "apoderado representante legal"
        )

    if any(
        palabra in pregunta_lower
        for palabra in palabras_cita
    ):
        partes_busqueda.append(
             "cita previa reserva enlace URL oficial "
            "Bookeo horarios turnos fechas disponibles "
            "mañana tarde sistema oficial de citas"
        )

    if any(
        palabra in pregunta_lower
        for palabra in palabras_plazo
    ):
        partes_busqueda.append(
            "tiempo estimado plazo demora entrega del trámite"
        )  

    if (
        intencion == "dni_consulta_estado"
        or state.get("tipo_consulta") == "seguimiento"
    ):
        partes_busqueda.append(
            "consulta estado trámite DNI RENIEC "
            "avance 100% entrega recoger portal oficial"
        )

    pregunta_busqueda = " ".join(
        partes_busqueda
    )

    return {
        **state,
        "pregunta_busqueda": pregunta_busqueda,
    }


def recuperar_documentos(
    state: DNIState,
) -> DNIState:
    """
    Recupera y filtra los fragmentos documentales según la
    intención actual.
    """
    state = {**state, "reglas_faltantes": []}
    intencion = state["intencion"]

    if state.get("requiere_aclaracion") or intencion in {
        "fuera_alcance",
        "general",
    }:
        return {
            **state,
            "fragmentos": [],
            "contexto": "",
            "fuentes": [],
        }

    if ruta_documental(state.get("contexto_canonico")) != intencion:
        return {**state, "fragmentos": [], "contexto": "", "fuentes": [],
                "intencion": "general", "requiere_aclaracion": True,
                "motivo_aclaracion": "tramite", "estado_documental": "pendiente_aclaracion"}

    pregunta_busqueda = state[
        "pregunta_busqueda"
    ]

    if intencion in ADULT_FILES and not plan_adulto(state['contexto_canonico']):
        return {**state, 'fragmentos': [], 'contexto': '', 'fuentes': [],
                'estado_documental': 'sin_evidencia'}

    fragmentos = recuperar_contexto(
        pregunta_busqueda,
        k=10,
    )

    if intencion in ADULT_FILES:
        plan = plan_adulto(state['contexto_canonico'])
        fragmentos_finales = []
        found = set()
        def seleccionar(candidates):
            for f in candidates:
                file = f.get('metadata', {}).get('archivo')
                if file not in plan:
                    continue
                for rule, content in re.findall(r'\[\[REGLA:([a-z_]+)\]\]\s*(.*?)\[\[FIN\]\]', f['contenido'], flags=re.S):
                    key = (file, rule)
                    if rule in plan[file] and key not in found:
                        found.add(key)
                        fragmentos_finales.append({**f, 'contenido': content,
                            'metadata': {**f['metadata'], 'regla': rule}})
        seleccionar(fragmentos)
        required = {(file, rule) for file, rules in plan.items() for rule in rules}
        # El top-k semántico no garantiza que incluya todas las reglas de un plan.
        # Reintento acotado, solo para reglas autorizadas; nunca relaja la completitud.
        for file, rule in sorted(required - found):
            if (file, rule) not in found:
                seleccionar(recuperar_contexto(
                    f'{pregunta_busqueda} Fuente {file} REGLA {rule}', k=10))
        if required - found:
            seleccionar(recuperar_reglas_exactas(state['contexto_canonico'], required - found))
        state['reglas_faltantes'] = [f'{file}#{rule}' for file, rule in sorted(required - found)]
        if not required or not required <= found:
            fragmentos_finales = []
    else:
        archivo_autorizado = DOCUMENTOS_POR_INTENCION.get(intencion)
        filtrados = [fragmento for fragmento in fragmentos
                     if archivo_autorizado and fragmento.get("metadata", {}).get("archivo") == archivo_autorizado]
        fragmentos_finales = filtrados[:6]

    contexto = "\n\n---\n\n".join(
        ((f"FUENTE: {fragmento['metadata']['archivo']} | REGLA: {fragmento['metadata']['regla']}\n"
          if 'regla' in fragmento['metadata'] else '') + fragmento["contenido"])
        for fragmento in fragmentos_finales
    )

    fuentes = [
        {
            "archivo": (
                fragmento["metadata"]["archivo"]
            ),
            "chunk": (
                fragmento["metadata"]["chunk"]
            ),
            "distancia": fragmento["score"],
            "recuperacion": fragmento["metadata"].get("recuperacion", "semantica"),
            **({"regla": fragmento["metadata"]["regla"]} if "regla" in fragmento["metadata"] else {}),
        }
        for fragmento in fragmentos_finales
    ]

    return {
        **state,
        "fragmentos": fragmentos_finales,
        "contexto": contexto,
        "fuentes": fuentes,
        "estado_documental": "disponible" if fragmentos_finales else "sin_evidencia",
    }


def construir_texto_historial(
    historial: list[dict],
) -> str:
    """
    Convierte las últimas interacciones en un texto breve
    para ayudar al modelo a interpretar las repreguntas.
    """
    if not historial:
        return (
            "No existe conversación anterior "
            "en esta sesión."
        )

    lineas = []

    for numero, turno in enumerate(
        historial[-3:],
        start=1,
    ):
        pregunta = turno.get(
            "pregunta",
            "",
        )

        respuesta = turno.get(
            "respuesta",
            "",
        )

        intencion = turno.get(
            "intencion",
            "",
        )

        lineas.append(
            f"Interacción anterior {numero}:\n"
            f"Intención: {intencion}\n"
            f"Ciudadano: {pregunta}\n"
            f"Asistente: {respuesta}"
        )

    return "\n\n".join(lineas)


def redactar_respuesta(
    state: DNIState,
) -> DNIState:
    """
    Genera una respuesta basada en el contexto documental.

    El historial se utiliza solamente para interpretar la
    conversación, nunca como fuente oficial.
    """
    controlled = respuesta_controlada(state)
    if controlled is not None:
        return {**state, "respuesta_borrador": controlled}

    intencion = state["intencion"]
    pregunta = state["pregunta"]
    pregunta_lower = pregunta.lower()
    historial = state.get(
        "historial",
        [],
    )

    if intencion == "fuera_alcance":
        respuesta = (
            "No cuento con información suficiente en las "
            "fuentes cargadas para responder sobre ese trámite. "
            "Este asistente piloto está limitado a consultas "
            "relacionadas con trámites de DNI cargados en la "
            "base documental."
        )

        return {
            **state,
            "respuesta_borrador": respuesta,
        }

    if intencion == "general" and state.get("estado_documental") == "no_documentado":
        identificacion = "de adulto" if state.get("contexto_solicitante", {}).get("grupo_edad") == "adulto" else "solicitado"
        return {**state, "respuesta_borrador": (
            f"Identifico el trámite de DNI {identificacion}. El corpus de este piloto "
            "no documenta sus requisitos, tarifas ni condiciones; no puedo "
            "proporcionarlos con respaldo suficiente. Por favor, consulte "
            "los canales oficiales del consulado."
        )}

    if intencion == "general" and state.get("requiere_aclaracion"):
        aclaraciones = {
            **ADULT_PREGUNTAS,
            "edad": "Indique si el titular del DNI es menor de 18 años o adulto.",
            "operacion": "Indique si es su primer DNI o la renovación de un DNI que ya tuvo.",
            "contradiccion": "Por favor, aclare un único trámite, si el titular es menor o adulto y si ya tuvo DNI.",
            "tramite": "Indique si desea orientación sobre DNI y cuál es el trámite solicitado.",
            "dni_previo": "¿Su hijo ya tiene un DNI peruano vencido o está solicitando su primer DNI?" if state.get("contexto_solicitante", {}).get("destinatario") == "descendiente" else "¿El titular ya tenía DNI peruano o está solicitando su primer DNI?",
            "titular": "¿De cuál de las personas mencionadas es el DNI que desea tramitar?",
            "documento": "¿El DNI mencionado es el que desea tramitar o es un documento de apoyo?",
            "tipo_dni": "¿Ya dispone de DNI amarillo y desea cambiarlo por el azul, o se refiere a otro trámite de DNI?",
        }
        return {**state, "respuesta_borrador": formular_aclaracion(state, aclaraciones[state["motivo_aclaracion"]])}

    if intencion == "general":
        respuesta = (
            "Para poder orientarle correctamente, indique si "
            "su consulta se refiere a la renovación del DNI "
            "de un menor, al DNI de un menor por primera vez "
            "o a la consulta del estado de un trámite de DNI."
        )

        return {
            **state,
            "respuesta_borrador": respuesta,
        }

    # Respuesta específica para cuando el usuario reclama que
    # ya proporcionó el contexto.
    if es_mensaje_sobre_contexto(
        pregunta_lower
    ):
        descripcion_tramite = {
            "dni_menor_renovacion": (
                "la renovación del DNI de su hijo menor"
            ),
            "dni_menor_primera_vez": (
                "el trámite de DNI de su hijo menor "
                "por primera vez"
            ),
            "dni_consulta_estado": (
                "la consulta del estado de su trámite de DNI"
            ),
        }

        tramite_descrito = descripcion_tramite.get(
            intencion,
            "el trámite de DNI indicado",
        )

        respuesta = (
            "Tiene razón. La conversación se refiere a "
            f"{tramite_descrito} y mantendré ese contexto "
            "durante esta sesión. Puede formular directamente "
            "su siguiente consulta sobre los requisitos, el "
            "costo, la cita o las condiciones del trámite."
        )

        return {
            **state,
            "respuesta_borrador": respuesta,
        }

    if intencion in ADULT_FILES and not plan_adulto(state['contexto_canonico']):
        return {**state, 'respuesta_borrador': (
            'La combinación solicitada no está confirmada en las fichas aportadas. '
            'No puedo proporcionar requisitos combinados ni sumar tasas. '
            'En rectificación de datos con renovación, indique si el DNI está vencido; '
            'la combinación con cambio de estado civil requiere confirmación del Consulado.')}

    if not state.get("contexto") and state.get('reglas_faltantes'):
        return {**state, 'respuesta_borrador': (
            'No cuento con información documental suficiente: la consulta ya está identificada, '
            'pero faltan reglas verificables en la recuperación. Es necesario revisar el corpus o el índice; '
            'no puedo sustituirlas por requisitos de otro procedimiento.')}

    if not state.get("contexto"):
        respuesta = (
            "No cuento con información documental suficiente "
            "para responder con seguridad. Por favor, reformule "
            "la pregunta indicando el trámite de DNI al que "
            "se refiere."
        )

        return {
            **state,
            "respuesta_borrador": respuesta,
        }

    if intencion in ADULT_FILES and 'OBSERVACIÓN PENDIENTE' in state.get('contexto', ''):
        return {**state, 'respuesta_borrador': (
            'La ficha aportada contiene una observación documental pendiente. '
            'No puedo confirmar una lista definitiva de documentos para este supuesto. '
            + '\n\n'.join(f['contenido'] for f in state['fragmentos']
                if 'OBSERVACIÓN PENDIENTE' in f['contenido'])
            + '\nConfirme esta documentación con el Consulado antes de presentar el trámite.')}

    respuesta_breve = respuesta_contextual(state)
    if respuesta_breve is not None:
        return {**state, "respuesta_borrador": respuesta_breve}

    historial_texto = construir_texto_historial(
        [] if intencion in ADULT_FILES else historial
    )

    llm = LLMService()

    prompt = f"""
Eres un asistente consular especializado en trámites de DNI.
Si las fuentes contienen una OBSERVACIÓN PENDIENTE, explica la incertidumbre;
no conviertas alternativas ambiguas en requisitos acumulativos. No sumes tasas.
No infieras cantidades de fotos, plazos ni apostillas ausentes en las fuentes.
Atribuye los requisitos a las fuentes incluidas; no uses condiciones de otra regla.

Debes responder únicamente usando la información incluida en el CONTEXTO
DOCUMENTAL.

El HISTORIAL DE LA CONVERSACIÓN sirve únicamente para interpretar referencias,
pronombres o repreguntas del ciudadano. No debes utilizar el historial como
fuente oficial de requisitos, costos, enlaces ni condiciones.

Si el ciudadano formuló anteriormente una pregunta y la consulta actual
solamente aporta la aclaración necesaria para responderla, responde primero
la pregunta anterior utilizando la nueva información.

Si el último mensaje del asistente ofreció proporcionar requisitos,
procedimiento, costo, cita u otra información concreta, y el ciudadano
responde afirmativamente con expresiones como "sí", "sí por favor",
"de acuerdo", "correcto" o "adelante", proporciona inmediatamente la
información ofrecida.

No vuelvas a preguntar si desea recibir esa misma información.

Ejemplo:
- Asistente: ¿Desea que le proporcione los requisitos para el DNI de menor
  por primera vez?
- Ciudadano: Sí, por favor.
- Respuesta esperada: proporciona directamente los requisitos completos.

No repitas todos los requisitos del trámite cuando el ciudadano únicamente
esté aclarando el tipo de DNI, salvo que solicite expresamente los requisitos.

Ejemplo:
- Pregunta anterior: ¿Cuánto demora en llegar el DNI?
- Aclaración actual: Es la renovación del DNI de mi hijo.
- Respuesta esperada: informa principalmente el plazo de entrega aplicable,
  sin volver a enumerar todos los requisitos.

Cuando la pregunta sea una repregunta breve, utiliza la INTENCIÓN CLASIFICADA
y el HISTORIAL para comprender a qué trámite se refiere el ciudadano. La
información concreta de la respuesta debe proceder siempre del CONTEXTO
DOCUMENTAL.

Cuando la pregunta sea sobre consulta de estado y el ciudadano quiera
proporcionar su número de DNI:
- No digas que falta información en las fuentes.
- Indica que el asistente no puede recibir ni consultar números de DNI.
- Orienta al ciudadano a consultar personalmente en el portal oficial
  de RENIEC.

No inventes requisitos, correos electrónicos, montos, enlaces ni condiciones
que no estén en el CONTEXTO DOCUMENTAL.

No deduzcas excepciones ni condiciones legales que no aparezcan expresamente
en el CONTEXTO DOCUMENTAL. Si la fuente exige la presencia de un padre o
apoderado legal, limita la respuesta a esa condición.

No afirmes que un hermano, familiar o tercero puede representar al menor,
salvo que el CONTEXTO DOCUMENTAL indique expresamente que puede actuar como
apoderado o representante legal.

Cuando la pregunta solicite requisitos:
- Busca explícitamente la sección "Requisitos" del CONTEXTO DOCUMENTAL.
- Enumera solamente los requisitos indicados en esa sección.
- No sustituyas requisitos por advertencias o condiciones especiales.

Cuando la pregunta solicite costo, precio, pago, tasa o monto:
- Busca explícitamente las secciones "Requisitos" y "Costo".
- Responde el importe exacto si aparece en el CONTEXTO DOCUMENTAL.
- Si aparece una tasa consular, puedes indicarla como costo del trámite.
- No inventes importes.

Cuando la pregunta solicite cita, enlace, días u horarios de atención:
- Copia literalmente la URL oficial incluida en el CONTEXTO DOCUMENTAL.
- No modifiques, resumas ni acortes la URL.
- Coloca la URL en una línea independiente.
- Si el ciudadano pregunta si existen citas por la mañana o por la tarde,
  indica que los días y horarios disponibles deben consultarse directamente
  en el sistema oficial de reserva de citas.
- No confirmes que existe atención en un horario determinado si esa
  disponibilidad no aparece expresamente en el CONTEXTO DOCUMENTAL.
- No inventes días, horas ni turnos.

Cuando la pregunta sea sobre consulta de estado, avance, ficha, observación,
subsanación, entrega o recojo del DNI:
- Indica que el ciudadano debe consultar personalmente el estado en el portal
  oficial de RENIEC.
- Copia literalmente la URL oficial incluida en el CONTEXTO DOCUMENTAL.
- Indica que debe ingresar su número de DNI directamente en el portal oficial.
- No solicites el número de DNI dentro del asistente.
- No afirmes que el DNI está listo, observado o disponible si esa información
  no aparece en el CONTEXTO DOCUMENTAL.
- Si corresponde, indica que debe verificar que el avance alcance el 100%
  antes de acudir a recogerlo.

Si el CONTEXTO DOCUMENTAL contiene trámites parecidos:
- La INTENCIÓN CLASIFICADA y el trámite autorizado ya están decididos. No los
  cambies a partir del historial. El cambio amarillo a azul (azul por primera
  vez) no significa primera inscripción: describe únicamente el supuesto de
  cumplir 17 años con DNI amarillo incluido en su documento específico.
- Si el menor nunca tuvo DNI, corresponde al DNI de menor por primera vez.
- Si la intención es renovación de menor, utiliza únicamente su documentación;
  la mera posesión previa de DNI no permite reclasificar amarillo a azul como renovación.

Cuando el ciudadano se despida o agradezca:
- Responde de forma breve y cordial.
- No repitas requisitos, enlaces, costos ni información ya proporcionada,
  salvo que el ciudadano la solicite nuevamente.

Responde únicamente al tema de la pregunta actual: para una consulta de costo,
indica el importe y su alcance sin enumerar requisitos; para plazo o fotografías,
limita la respuesta a ese tema. No repitas información extensa del historial
salvo petición expresa. Reconoce brevemente una dificultad comunicada sin
inventar su causa, fechas, plazas disponibles ni acciones de reserva.

Responde en español claro, con tono formal y orientativo.
No uses información externa al CONTEXTO DOCUMENTAL.

HISTORIAL DE LA CONVERSACIÓN:
{historial_texto}

INTENCIÓN ANTERIOR:
{state.get("intencion_anterior", "No disponible")}

INTENCIÓN CLASIFICADA:
{state["intencion"]}

CONTEXTO DOCUMENTAL:
{state["contexto"]}

PREGUNTA ACTUAL DEL CIUDADANO:
{state["pregunta"]}

RESPUESTA:
"""

    respuesta = llm.generar_respuesta(
        prompt
    )

    return {
        **state,
        "respuesta_borrador": respuesta,
    }


def verificar_respuesta(
    state: DNIState,
) -> DNIState:
    """
    Verifica la respuesta y añade la interacción actual
    al historial temporal de la sesión.
    """
    respuesta = state["respuesta_borrador"]
    controlled = respuesta_controlada(state)
    replaced = controlled is not None and respuesta != controlled
    if replaced:
        respuesta = controlled
    respuesta_lower = respuesta.lower()
    intencion = state["intencion"]

    advertencias = []
    if replaced:
        advertencias.append("Borrador sustituido por el control determinista de alcance documental.")

    if "@" in respuesta:
        advertencias.append(
            "La respuesta contiene un correo electrónico "
            "no esperado."
        )

    if intencion == "dni_consulta_estado":
        if (
            "número de dni" in respuesta_lower
            and "portal" not in respuesta_lower
        ):
            advertencias.append(
                "La respuesta menciona número de DNI "
                "sin redirigir al portal oficial."
            )

    if intencion == "general":
        marcadores_aclaracion = [
            "indique si",
            "por favor",
            "reformule",
            "para poder orientarle",
        ]

        if not any(
            marcador in respuesta_lower
            for marcador in marcadores_aclaracion
        ):
            advertencias.append(
                "La intención es general, pero la respuesta "
                "no solicita información suficiente."
            )

    verificacion = (
        "ok"
        if not advertencias
        else (
            "observada: "
            + " | ".join(advertencias)
        )
    )

    if not advertencias and (state.get('estado_documental') == 'sin_evidencia' or controlled == COMMON_CONFLICT):
        details = ('disposiciones comunes inconsistentes' if controlled == COMMON_CONFLICT else
                   ', '.join(state.get('reglas_faltantes', [])) or 'fuentes insuficientes o combinación no autorizada')
        verificacion = 'abstencion_documental: ' + details

    historial_anterior = state.get(
        "historial",
        [],
    )

    turno_actual = {
        "pregunta": state["pregunta"],
        "respuesta": respuesta,
        "intencion": intencion,
    }

    historial_actualizado = (
        historial_anterior + [turno_actual]
    )[-MAX_TURNOS_HISTORIAL:]

    return {
        **state,
        "verificacion": verificacion,
        "respuesta_borrador": respuesta,
        "respuesta_final": respuesta,
        "historial": historial_actualizado,
    }


def redactar_respuesta_minimizada(state: DNIState) -> DNIState:
    # La pregunta almacenada no se duplica ni se sustituye en el historial.
    # Solo la entrada al redactor recupera el tema pendiente ya aclarado.
    entrada = {**state, "pregunta": pregunta_contextual(state)}
    if not state.get("requiere_aclaracion") and state.get("intencion") not in {"general", "fuera_alcance"} and ruta_documental(state.get("contexto_canonico")) != state.get("intencion"):
        entrada.update(intencion="general", requiere_aclaracion=True,
                       motivo_aclaracion="tramite", estado_documental="pendiente_aclaracion")
    if state.get("requiere_aclaracion"):
        entrada["intencion"] = "general"
    if entrada.get("intencion") in {"general", "fuera_alcance"}:
        entrada.update(contexto="", fuentes=[], fragmentos=[])
    resultado = redactar_respuesta(entrada)
    resultado["pregunta"] = state["pregunta"]
    resultado["respuesta_borrador"] = minimizar_texto(resultado["respuesta_borrador"], permitir_oficiales=True)
    return resultado


def construir_grafo_dni():
    """
    Construye el flujo LangGraph con memoria temporal.

    La memoria se conserva por session_id mientras el proceso
    Python permanezca activo. Al reiniciar el servidor, se elimina.
    """
    workflow = StateGraph(DNIState)

    workflow.add_node(
        "clasificar_intencion",
        clasificar_intencion,
    )

    workflow.add_node(
        "enriquecer_busqueda",
        enriquecer_busqueda,
    )

    workflow.add_node(
        "recuperar_documentos",
        recuperar_documentos,
    )

    workflow.add_node(
        "redactar_respuesta",
        redactar_respuesta_minimizada,
    )

    workflow.add_node(
        "verificar_respuesta",
        verificar_respuesta,
    )

    workflow.set_entry_point(
        "clasificar_intencion"
    )

    workflow.add_edge(
        "clasificar_intencion",
        "enriquecer_busqueda",
    )

    workflow.add_edge(
        "enriquecer_busqueda",
        "recuperar_documentos",
    )

    workflow.add_edge(
        "recuperar_documentos",
        "redactar_respuesta",
    )

    workflow.add_edge(
        "redactar_respuesta",
        "verificar_respuesta",
    )

    workflow.add_edge(
        "verificar_respuesta",
        END,
    )

    memoria_temporal = InMemorySaver()

    return workflow.compile(
        checkpointer=memoria_temporal
    )
