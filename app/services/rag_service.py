from app.graph.dni_graph import construir_grafo_dni
from app.services.log_service import registrar_consulta


class RAGService:
    def __init__(self):
        self.grafo = construir_grafo_dni()

    def responder(
        self,
        pregunta: str,
        session_id: str,
    ) -> dict:
        config = {
            "configurable": {
                "thread_id": session_id,
            }
        }

        resultado = self.grafo.invoke(
            {
                "pregunta": pregunta,
            },
            config=config,
        )

        respuesta = resultado["respuesta_final"]
        fuentes = resultado.get("fuentes", [])
        intencion = resultado.get(
            "intencion",
            "general",
        )
        verificacion = resultado.get(
            "verificacion",
            "sin_verificacion",
        )

        registrar_consulta(
            pregunta=pregunta,
            respuesta=respuesta,
            intencion=intencion,
            verificacion=verificacion,
            fuentes=fuentes,
        )

        return {
            "session_id": session_id,
            "respuesta": respuesta,
            "fuentes": fuentes,
            "intencion": intencion,
            "verificacion": verificacion,
        }