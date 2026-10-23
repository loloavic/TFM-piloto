from uuid import uuid4

from app.core.config import settings
from app.core.privacy import minimizar_texto
from app.services.session_service import SessionStore

from app.graph.dni_graph import construir_grafo_dni
from app.services.log_service import registrar_consulta


class RAGService:
    def __init__(self):
        self.grafo = construir_grafo_dni()
        self.sessions = SessionStore(
            self.grafo.checkpointer.delete_thread,
            settings.session_ttl_seconds, settings.session_max_count,
        )

    def responder(
        self,
        pregunta: str,
        session_id: str | None = None,
        session_token: str | None = None,
    ) -> dict:
        self.sessions.start(settings.session_cleanup_interval_seconds)
        session_id = session_id or str(uuid4())
        with self.sessions.access(session_id, session_token) as token:
            resultado = self.grafo.invoke(
                {"pregunta": minimizar_texto(pregunta)},
                config={"configurable": {"thread_id": session_id}},
            )
            respuesta = minimizar_texto(resultado["respuesta_final"])
            fuentes = resultado.get("fuentes", [])
            intencion = resultado.get("intencion", "general")
            verificacion = resultado.get("verificacion", "sin_verificacion")
            registrar_consulta(
                pregunta="", respuesta="", intencion=intencion,
                verificacion=verificacion, fuentes=fuentes,
            )
            return {
                "session_id": session_id, "session_token": token,
                "respuesta": respuesta, "fuentes": fuentes,
                "intencion": intencion, "verificacion": verificacion,
            }
