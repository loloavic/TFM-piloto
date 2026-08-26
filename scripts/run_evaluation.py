import sys
from pathlib import Path

import pandas as pd

# Agrega la raíz del proyecto al path de Python
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.services.rag_service import RAGService


CASOS_PRUEBA = [
    {
        "codigo": "P01",
        "caso": "Requisitos renovación DNI menor",
        "pregunta": "¿Qué requisitos necesito para renovar el DNI de mi menor hijo?",
        "intencion_esperada": "dni_menor_renovacion",
    },
    {
        "codigo": "P02",
        "caso": "Cita renovación DNI menor",
        "pregunta": "Necesito sacar una cita para el renuevo de DNI de mi menor hijo.",
        "intencion_esperada": "dni_menor_renovacion",
    },
    {
        "codigo": "P03",
        "caso": "DNI menor por primera vez",
        "pregunta": "¿Qué requisitos necesito para tramitar el DNI de mi menor hijo por primera vez?",
        "intencion_esperada": "dni_menor_primera_vez",
    },
    {
        "codigo": "P04",
        "caso": "Costo DNI menor primera vez",
        "pregunta": "¿Cuál es el costo del DNI de menor por primera vez?",
        "intencion_esperada": "dni_menor_primera_vez",
    },
    {
        "codigo": "P05",
        "caso": "Consulta de estado",
        "pregunta": "¿Puedo darte mi número de DNI para que consultes si ya llegó?",
        "intencion_esperada": "dni_consulta_estado",
    },
    {
        "codigo": "P06",
        "caso": "Fuera de alcance",
        "pregunta": "Necesito renovar mi pasaporte.",
        "intencion_esperada": "fuera_alcance",
    },
]


def ejecutar_evaluacion() -> pd.DataFrame:
    rag = RAGService()
    resultados = []

    for caso in CASOS_PRUEBA:
        resultado = rag.responder(caso["pregunta"])

        cumple_intencion = (
            resultado["intencion"] == caso["intencion_esperada"]
        )

        cumple_verificacion = (
            resultado["verificacion"] == "ok"
        )

        cumple = cumple_intencion and cumple_verificacion

        resultados.append(
            {
                "codigo": caso["codigo"],
                "caso": caso["caso"],
                "pregunta": caso["pregunta"],
                "intencion_esperada": caso["intencion_esperada"],
                "intencion_obtenida": resultado["intencion"],
                "verificacion": resultado["verificacion"],
                "numero_fuentes": len(resultado["fuentes"]),
                "cumple_intencion": cumple_intencion,
                "cumple_verificacion": cumple_verificacion,
                "cumple": cumple,
                "respuesta": resultado["respuesta"],
            }
        )

    return pd.DataFrame(resultados)


def main():
    df_resultados = ejecutar_evaluacion()

    ruta_salida = Path("data/logs/evaluacion_casos_prueba.csv")
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)

    df_resultados.to_csv(
        ruta_salida,
        index=False,
        encoding="utf-8",
    )

    total = len(df_resultados)
    correctos = int(df_resultados["cumple"].sum())

    print("=" * 80)
    print("EVALUACIÓN FUNCIONAL DEL ASISTENTE")
    print("=" * 80)
    print(f"Casos evaluados: {total}")
    print(f"Casos correctos: {correctos}")
    print(f"Tasa de cumplimiento: {(correctos / total) * 100:.2f}%")
    print(f"Archivo generado: {ruta_salida}")
    print("=" * 80)

    print(
        df_resultados[
            [
                "codigo",
                "intencion_esperada",
                "intencion_obtenida",
                "verificacion",
                "numero_fuentes",
                "cumple",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()