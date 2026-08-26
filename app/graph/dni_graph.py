from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, StateGraph

from app.graph.state import DNIState
from app.rag.retriever import recuperar_contexto
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


def clasificar_intencion(
    state: DNIState,
) -> DNIState:
    """
    Clasifica la intención de la consulta actual.

    Cuando la pregunta no expresa una nueva intención, conserva
    automáticamente el trámite activo dentro de la misma sesión.
    """
    pregunta = state["pregunta"].strip()
    pregunta_lower = pregunta.lower()

    niega_primera_vez = any(
        expresion in pregunta_lower
        for expresion in [
            "no es dni por primera vez",
            "no es por primera vez",
            "no es primera vez",
            "no es su primer dni",
            "no necesita su primer dni",
            "ya tuvo dni",
            "ya tiene dni",
        ]
    )

    niega_renovacion = any(
        expresion in pregunta_lower
        for expresion in [
            "no debo renovar",
            "no debe renovar",
            "no quiero renovar",
            "no es renovación",
            "no es renovacion",
            "no corresponde renovar",
            "nunca tuvo dni",
            "nunca ha tenido dni",
            "no tuvo dni",
        ]
    )

    # El estado recuperado por LangGraph puede contener la intención
    # y el trámite de la interacción anterior.
    intencion_previa = state.get("intencion")
    tramite_previo = state.get("tramite_actual")

    palabras_fuera_alcance = [
        "pasaporte",
        "visa",
        "visado",
        "carnet de extranjería",
        "carnet de extranjeria",
        "licencia de conducir",
        "apostilla",
        "carta poder",
        "poder consular",
        "matrimonio",
        "defunción",
        "defuncion",
    ]

    palabras_estado = [
        "estado del trámite",
        "estado del tramite",
        "estado de mi trámite",
        "estado de mi tramite",
        "seguimiento",
        "avance",
        "ya está listo",
        "ya esta listo",
        "si está listo",
        "si esta listo",
        "consultar mi dni",
        "consultar el dni",
        "consultar trámite",
        "consultar tramite",
        "ver mi trámite",
        "ver mi tramite",
        "recoger mi dni",
        "entrega de dni",
        "ya llegó",
        "ya llego",
        "número de ficha",
        "numero de ficha",
        "ficha reniec",
        "reniec",
        "observado",
        "subsanado",
        "100%",
        "cuánto demora",
        "cuanto demora",
        "cuánto tarda",
        "cuanto tarda",
        "tiempo de entrega",
        "plazo de entrega",
        "después de tramitarlo",
        "despues de tramitarlo",
        "cuándo llega",
        "cuando llega",
    ]

    palabras_primera_vez = [
        "primera vez",
        "por primera vez",
        "nunca tuvo dni",
        "nunca ha tenido dni",
        "no tuvo dni",
        "no tiene dni",
        "sacar dni por primera vez",
        "tramitar su primer dni",
        "obtener su primer dni",
        "primera inscripción",
        "primera inscripcion",
    ]

    palabras_renovacion = [
        "renovar",
        "renovación",
        "renovacion",
        "renuevo",
        "actualizar dni",
        "ya tuvo dni",
        "ya tiene dni",
        "dni vencido",
        "dni caducado",
    ]

    indicadores_primera_vez_fuertes = [
        "nunca tuvo dni",
        "nunca ha tenido dni",
        "no tuvo dni",
        "no tiene dni",
        "primer dni",
        "primera inscripción",
        "primera inscripcion",
    ]

    indicadores_renovacion_fuertes = [
        "ya tuvo dni",
        "ya tiene dni",
        "dni vencido",
        "está vencido",
        "esta vencido",
        "dni caducado",
        "está caducado",
        "esta caducado",
    ]

    es_primera_vez_fuerte = any(
        expresion in pregunta_lower
        for expresion in indicadores_primera_vez_fuertes
    )

    es_renovacion_fuerte = any(
        expresion in pregunta_lower
        for expresion in indicadores_renovacion_fuertes
    )

    es_fuera_alcance = any(
        palabra in pregunta_lower
        for palabra in palabras_fuera_alcance
    )

    es_estado = any(
        palabra in pregunta_lower
        for palabra in palabras_estado
    )

    es_primera_vez = any(
        palabra in pregunta_lower
        for palabra in palabras_primera_vez
    )

    es_renovacion = any(
        palabra in pregunta_lower
        for palabra in palabras_renovacion
    )

    # Las intenciones explícitas de la pregunta actual
    # tienen prioridad sobre el contexto anterior.
    if es_fuera_alcance:
        intencion = "fuera_alcance"

    elif es_estado:
        intencion = "dni_consulta_estado"

    # Ejemplo:
    # "No es primera vez, ya tiene DNI y está vencido."
    elif (
        es_renovacion_fuerte
        and not niega_renovacion
    ):
        intencion = "dni_menor_renovacion"

    # Ejemplo:
    # "No debo renovar porque nunca tuvo DNI."
    elif (
        es_primera_vez_fuerte
        and not niega_primera_vez
    ):
        intencion = "dni_menor_primera_vez"

    elif (
        es_primera_vez
        and not niega_primera_vez
        and not es_renovacion
    ):
        intencion = "dni_menor_primera_vez"

    elif (
        es_renovacion
        and not niega_renovacion
        and not es_primera_vez
    ):
        intencion = "dni_menor_renovacion"

    else:
        intencion = "general"

    intenciones_contextuales_validas = {
        "dni_menor_renovacion",
        "dni_menor_primera_vez",
        "dni_consulta_estado",
    }

    # Si la pregunta no contiene una intención nueva, se conserva
    # automáticamente el trámite activo de la sesión.
    #
    # Esto permite interpretar consultas como:
    # - ¿Puede acompañarlo su hermano?
    # - ¿Y cuánto cuesta?
    # - ¿Me ayuda con la cita?
    # - Ya le dije de qué trámite se trata.
    if (
        intencion == "general"
        and intencion_previa
        in intenciones_contextuales_validas
    ):
        intencion = intencion_previa

    if intencion in intenciones_contextuales_validas:
        tramite_actual = intencion

    elif intencion == "fuera_alcance":
        tramite_actual = ""

    else:
        tramite_actual = tramite_previo or ""

    return {
        **state,
        "pregunta": pregunta,
        "intencion_anterior": (
            intencion_previa or ""
        ),
        "intencion": intencion,
        "tramite_actual": tramite_actual,
    }


def enriquecer_busqueda(
    state: DNIState,
) -> DNIState:
    """
    Construye una búsqueda RAG contextualizada.

    Añade el trámite identificado para evitar que una repregunta
    breve recupere documentos pertenecientes a otro procedimiento.
    """
    pregunta = state["pregunta"]
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

    palabras_estado = [
        "estado",
        "seguimiento",
        "avance",
        "listo",
        "recoger",
        "entrega",
        "ficha",
        "reniec",
        "observado",
        "subsanado",
    ]

    descripcion_intencion = {
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
    }

    partes_busqueda = [pregunta]

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
            "tiempo estimado plazo demora entrega "
            "seguimiento RENIEC avance 100%"
        )  

    if (
        intencion == "dni_consulta_estado"
        or any(
            palabra in pregunta_lower
            for palabra in palabras_estado
        )
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
    intencion = state["intencion"]

    if intencion in {
        "fuera_alcance",
        "general",
    }:
        return {
            **state,
            "fragmentos": [],
            "contexto": "",
            "fuentes": [],
        }

    pregunta_busqueda = state[
        "pregunta_busqueda"
    ]

    fragmentos = recuperar_contexto(
        pregunta_busqueda,
        k=10,
    )

    if intencion == "dni_consulta_estado":
        filtrados = [
            fragmento
            for fragmento in fragmentos
            if "consulta_estado"
            in fragmento["metadata"]["archivo"]
        ]

    elif intencion == "dni_menor_primera_vez":
        filtrados = [
            fragmento
            for fragmento in fragmentos
            if "primera_vez"
            in fragmento["metadata"]["archivo"]
        ]

    elif intencion == "dni_menor_renovacion":
        filtrados = [
            fragmento
            for fragmento in fragmentos
            if "renovacion"
            in fragmento["metadata"]["archivo"]
        ]

    else:
        filtrados = []

    fragmentos_finales = filtrados[:6]

    contexto = "\n\n---\n\n".join(
        fragmento["contenido"]
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
        }
        for fragmento in fragmentos_finales
    ]

    return {
        **state,
        "fragmentos": fragmentos_finales,
        "contexto": contexto,
        "fuentes": fuentes,
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

    historial_texto = construir_texto_historial(
        historial
    )

    llm = LLMService()

    prompt = f"""
Eres un asistente consular especializado en trámites de DNI.

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
- Si el menor nunca tuvo DNI, corresponde al DNI de menor por primera vez.
- Si el menor ya tuvo DNI, corresponde a renovación de DNI de menor.

Cuando el ciudadano se despida o agradezca:
- Responde de forma breve y cordial.
- No repitas requisitos, enlaces, costos ni información ya proporcionada,
  salvo que el ciudadano la solicite nuevamente.

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
    respuesta_lower = respuesta.lower()
    intencion = state["intencion"]

    advertencias = []

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
        "respuesta_final": respuesta,
        "historial": historial_actualizado,
    }


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
        redactar_respuesta,
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