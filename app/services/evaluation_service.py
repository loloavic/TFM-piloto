import json
from pathlib import Path

import pandas as pd


LOG_PATH = Path("data/logs/consultas_log.csv")


def cargar_log_consultas(ruta_log: str | Path = LOG_PATH) -> pd.DataFrame:
    ruta_log = Path(ruta_log)

    if not ruta_log.exists():
        return pd.DataFrame(
            columns=[
                "fecha_hora",
                "pregunta",
                "intencion",
                "verificacion",
                "respuesta",
                "fuentes",
            ]
        )

    df = pd.read_csv(ruta_log)

    columnas_requeridas = [
        "fecha_hora",
        "pregunta",
        "intencion",
        "verificacion",
        "respuesta",
        "fuentes",
    ]

    for columna in columnas_requeridas:
        if columna not in df.columns:
            df[columna] = ""

    return df


def generar_resumen_evaluacion(ruta_log: str | Path = LOG_PATH) -> dict:
    df = cargar_log_consultas(ruta_log)

    total_consultas = len(df)

    if df.empty:
        resumen_intenciones = pd.DataFrame(
            columns=["intencion", "cantidad"]
        )
        resumen_verificacion = pd.DataFrame(
            columns=["verificacion", "cantidad"]
        )
        consultas_fuera_alcance = 0
        consultas_observadas = 0
    else:
        resumen_intenciones = (
            df["intencion"]
            .fillna("sin_intencion")
            .value_counts()
            .rename_axis("intencion")
            .reset_index(name="cantidad")
        )

        resumen_verificacion = (
            df["verificacion"]
            .fillna("sin_verificacion")
            .value_counts()
            .rename_axis("verificacion")
            .reset_index(name="cantidad")
        )

        consultas_fuera_alcance = int(
            (df["intencion"] == "fuera_alcance").sum()
        )

        consultas_observadas = int(
            df["verificacion"]
            .astype(str)
            .str.startswith("observada")
            .sum()
        )

    return {
        "total_consultas": int(total_consultas),
        "consultas_fuera_alcance": consultas_fuera_alcance,
        "consultas_observadas": consultas_observadas,
        "resumen_intenciones": resumen_intenciones,
        "resumen_verificacion": resumen_verificacion,
        "detalle": df,
    }


def extraer_archivos_fuente(fuentes_json: str) -> list[str]:
    try:
        fuentes = json.loads(fuentes_json)
    except Exception:
        return []

    archivos = []

    for fuente in fuentes:
        archivo = fuente.get("archivo")
        if archivo:
            archivos.append(archivo)

    return archivos


def generar_resumen_fuentes(ruta_log: str | Path = LOG_PATH) -> pd.DataFrame:
    df = cargar_log_consultas(ruta_log)

    registros = []

    for _, fila in df.iterrows():
        archivos = extraer_archivos_fuente(fila.get("fuentes", "[]"))

        for archivo in archivos:
            registros.append(
                {
                    "pregunta": fila["pregunta"],
                    "intencion": fila["intencion"],
                    "archivo_fuente": archivo,
                }
            )

    if not registros:
        return pd.DataFrame(
            columns=["archivo_fuente", "cantidad"]
        )

    df_fuentes = pd.DataFrame(registros)

    return (
        df_fuentes["archivo_fuente"]
        .value_counts()
        .rename_axis("archivo_fuente")
        .reset_index(name="cantidad")
    )