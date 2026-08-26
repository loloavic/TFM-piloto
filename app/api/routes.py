from uuid import uuid4

from fastapi import APIRouter

from app.models import (
    ConsultaRequest,
    ConsultaResponse,
    EvaluacionResumenResponse,
    ConteoResponse,
    ConsultaLogResponse,
    ConsultasLogResponse,
)
from app.services.evaluation_service import (
    generar_resumen_evaluacion,
    cargar_log_consultas,
)
from app.services.rag_service import RAGService


router = APIRouter(
    prefix="/api/v1",
    tags=["Consultas"],
)


# Se crea una única instancia del servicio.
# Esto es imprescindible para conservar la memoria temporal
# entre diferentes solicitudes de una misma conversación.
rag = RAGService()


@router.post(
    "/consultas",
    response_model=ConsultaResponse,
)
def crear_consulta(
    consulta: ConsultaRequest,
):
    # Si la interfaz envía un session_id, se reutiliza.
    # Si es la primera consulta, se genera uno nuevo.
    session_id = (
        consulta.session_id
        if consulta.session_id
        else str(uuid4())
    )

    resultado = rag.responder(
        pregunta=consulta.pregunta,
        session_id=session_id,
    )

    return ConsultaResponse(
        id_consulta=str(uuid4()),
        session_id=session_id,
        pregunta=consulta.pregunta,
        estado="respondida_con_langgraph_rag",
        respuesta=resultado["respuesta"],
        intencion=resultado["intencion"],
        verificacion=resultado["verificacion"],
        fuentes=resultado["fuentes"],
    )


@router.get(
    "/evaluacion/resumen",
    response_model=EvaluacionResumenResponse,
)
def obtener_resumen_evaluacion():
    resumen = generar_resumen_evaluacion()

    resumen_intenciones = [
        ConteoResponse(
            categoria=str(fila["intencion"]),
            cantidad=int(fila["cantidad"]),
        )
        for _, fila in resumen[
            "resumen_intenciones"
        ].iterrows()
    ]

    resumen_verificacion = [
        ConteoResponse(
            categoria=str(fila["verificacion"]),
            cantidad=int(fila["cantidad"]),
        )
        for _, fila in resumen[
            "resumen_verificacion"
        ].iterrows()
    ]

    return EvaluacionResumenResponse(
        total_consultas=resumen["total_consultas"],
        consultas_fuera_alcance=resumen[
            "consultas_fuera_alcance"
        ],
        consultas_observadas=resumen[
            "consultas_observadas"
        ],
        resumen_intenciones=resumen_intenciones,
        resumen_verificacion=resumen_verificacion,
    )


@router.get(
    "/evaluacion/consultas",
    response_model=ConsultasLogResponse,
)
def obtener_consultas_registradas(
    limite: int = 10,
):
    df = cargar_log_consultas()

    if df.empty:
        return ConsultasLogResponse(
            total=0,
            consultas=[],
        )

    df_ultimas = (
        df.tail(limite)
        .sort_index(ascending=False)
    )

    consultas = [
        ConsultaLogResponse(
            fecha_hora=str(fila["fecha_hora"]),
            pregunta=str(fila["pregunta"]),
            intencion=str(fila["intencion"]),
            verificacion=str(fila["verificacion"]),
            respuesta=str(fila["respuesta"]),
            fuentes=str(fila["fuentes"]),
        )
        for _, fila in df_ultimas.iterrows()
    ]

    return ConsultasLogResponse(
        total=len(df),
        consultas=consultas,
    )