from uuid import uuid4

import gradio as gr

from app.services.rag_service import RAGService
from app.core.config import settings
from app.core.privacy import minimizar_texto
from app.services.session_service import SesionNoAutorizada


# Se crea una sola instancia del servicio para mantener
# la memoria temporal de las diferentes sesiones.
rag = RAGService()


def generar_session_id() -> dict:
    """
    Genera un identificador único para una conversación.
    """
    return {"id": str(uuid4()), "token": None}


def responder_consulta(
    pregunta: str,
    historial: list[dict] | None,
    session_id: dict | None,
):
    """
    Procesa una consulta, conserva el historial visual de Gradio
    y reutiliza el mismo session_id en las repreguntas.
    """
    historial = historial or []

    if not pregunta or len(pregunta.strip()) < 3:
        return (
            "",
            historial,
            session_id or generar_session_id(),
            "",
            "Ingrese una consulta válida de al menos 3 caracteres.",
        )

    pregunta = minimizar_texto(pregunta.strip())

    # Si por alguna razón la sesión todavía no existe,
    # se genera una nueva.
    if not session_id:
        session_id = generar_session_id()

    try:
        resultado = rag.responder(
            pregunta=pregunta,
            session_id=session_id["id"],
            session_token=session_id["token"],
        )

        session_id = {"id": resultado["session_id"], "token": resultado["session_token"]}
        respuesta = resultado["respuesta"]

        # El formato actual de gr.Chatbot utiliza mensajes con
        # las propiedades role y content.
        historial_actualizado = historial + [
            {
                "role": "user",
                "content": pregunta,
            },
            {
                "role": "assistant",
                "content": respuesta,
            },
        ]

        fuentes = "\n".join(
            [
                (
                    f'- {fuente["archivo"]} | '
                    f'chunk {fuente["chunk"]} | '
                    f'distancia {fuente["distancia"]:.4f}'
                )
                for fuente in resultado["fuentes"]
            ]
        )

        if not fuentes:
            fuentes = (
                "No se recuperaron fuentes documentales "
                "para esta respuesta."
            )

        metadatos = (
            f'Intención clasificada: '
            f'{resultado["intencion"]}\n'
            f'Verificación: '
            f'{resultado["verificacion"]}\n'
            f'Sesión temporal: {session_id["id"]}'
        )

        return (
            "",
            historial_actualizado,
            session_id,
            fuentes,
            metadatos,
        )

    except Exception:
        mensaje_error = (
            "Se produjo un error al procesar la consulta. "
            "Revise que el entorno, el índice FAISS y la "
            "configuración del modelo estén disponibles."
        )

        historial_actualizado = historial + [
            {
                "role": "user",
                "content": pregunta,
            },
            {
                "role": "assistant",
                "content": mensaje_error,
            },
        ]

        metadatos = "Consulta no completada. Inicie una nueva conversación si la sesión caducó."

        return (
            "",
            historial_actualizado,
            session_id,
            "",
            metadatos,
        )


def eliminar_estado_sesion(estado):
    if estado and estado.get("token"):
        try:
            rag.sessions.delete(estado["id"], estado["token"])
        except SesionNoAutorizada:
            pass


def nueva_conversacion(estado=None):
    """
    Limpia la interfaz y genera un nuevo identificador.

    Al cambiar el session_id, LangGraph deja de recuperar
    el contexto de la conversación anterior.
    """
    eliminar_estado_sesion(estado)
    nuevo_session_id = generar_session_id()

    return (
        [],
        nuevo_session_id,
        "",
        "",
        (
            "Nueva conversación iniciada.\n"
            f"Sesión temporal: {nuevo_session_id['id']}"
        ),
    )


with gr.Blocks() as demo:
    gr.Markdown(
        """
# Asistente Consular DNI - Piloto TFM

Prototipo conversacional basado en **LangGraph y RAG** para orientar
sobre trámites de DNI en una oficina consular.

El asistente conserva temporalmente el contexto de la conversación para
atender repreguntas. No introduzca números de DNI ni otros datos personales.
"""
    )

    # Este estado no se muestra en la pantalla.
    # Gradio conserva su valor durante la sesión del usuario.
    session_id_state = gr.State(
        value=generar_session_id,
        time_to_live=settings.session_ttl_seconds,
        delete_callback=eliminar_estado_sesion,
    )

    chatbot = gr.Chatbot(
        label="Conversación",
        height=450,
        value=[],
    )

    pregunta = gr.Textbox(
        label="Consulta del ciudadano",
        placeholder=(
            "Ejemplo: ¿Qué requisitos necesito para "
            "renovar el DNI de mi menor hijo?"
        ),
        lines=3,
    )

    with gr.Row():
        boton_enviar = gr.Button(
            "Enviar consulta",
            variant="primary",
        )

        boton_nueva_conversacion = gr.Button(
            "Nueva conversación",
            variant="secondary",
        )

    with gr.Accordion(
        "Trazabilidad técnica",
        open=False,
    ):
        fuentes_output = gr.Textbox(
            label="Fuentes recuperadas",
            lines=6,
            interactive=False,
        )

        metadatos_output = gr.Textbox(
            label="Información del flujo",
            lines=4,
            interactive=False,
        )

    # Envío mediante el botón.
    boton_enviar.click(
        fn=responder_consulta,
        inputs=[
            pregunta,
            chatbot,
            session_id_state,
        ],
        outputs=[
            pregunta,
            chatbot,
            session_id_state,
            fuentes_output,
            metadatos_output,
        ],
    )

    # Envío mediante la tecla Enter.
    pregunta.submit(
        fn=responder_consulta,
        inputs=[
            pregunta,
            chatbot,
            session_id_state,
        ],
        outputs=[
            pregunta,
            chatbot,
            session_id_state,
            fuentes_output,
            metadatos_output,
        ],
    )

    # Inicio de una conversación independiente.
    boton_nueva_conversacion.click(
        fn=nueva_conversacion,
        inputs=[session_id_state],
        outputs=[
            chatbot,
            session_id_state,
            pregunta,
            fuentes_output,
            metadatos_output,
        ],
    )


if __name__ == "__main__":
    rag.sessions.start(settings.session_cleanup_interval_seconds)
    try:
        demo.launch()
    finally:
        rag.sessions.close()
