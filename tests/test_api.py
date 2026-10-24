import pytest

from uuid import UUID

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def comprobar_session_id_valido(
    session_id: str,
) -> None:
    """
    Comprueba que el identificador devuelto por la API
    tiene un formato UUID válido.
    """
    uuid_convertido = UUID(session_id)

    assert str(uuid_convertido) == session_id


def test_health():
    response = client.get("/health")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "ok"
    assert data["service"] == "asistente-consular-dni"
    assert "version" in data


@pytest.mark.integration
def test_consulta_requisitos_renovacion_dni_menor():
    payload = {
        "pregunta": (
            "¿Qué requisitos necesito para renovar "
            "el DNI de mi menor hijo?"
        )
    }

    response = client.post(
        "/api/v1/consultas",
        json=payload,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["estado"] == (
        "respondida_con_langgraph_rag"
    )

    assert data["intencion"] == (
        "dni_menor_renovacion"
    )

    assert data["verificacion"] == "ok"
    assert len(data["fuentes"]) > 0

    assert "session_id" in data
    assert data["session_id"]

    comprobar_session_id_valido(
        data["session_id"]
    )


@pytest.mark.integration
def test_consulta_costo_dni_menor_primera_vez():
    payload = {
        "pregunta": (
            "¿Cuál es el costo del DNI de menor "
            "por primera vez?"
        )
    }

    response = client.post(
        "/api/v1/consultas",
        json=payload,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["intencion"] == (
        "dni_menor_primera_vez"
    )

    assert data["verificacion"] == "ok"

    assert (
        "5.00" in data["respuesta"]
        or "5,00" in data["respuesta"]
        or "5 euros" in data["respuesta"].lower()
        or "5 €" in data["respuesta"]
    )

    assert "session_id" in data
    assert data["session_id"]

    comprobar_session_id_valido(
        data["session_id"]
    )


@pytest.mark.integration
def test_consulta_estado_no_recibe_dni():
    payload = {
        "pregunta": (
            "¿Puedo darte mi número de DNI para "
            "que consultes si ya llegó?"
        )
    }

    response = client.post(
        "/api/v1/consultas",
        json=payload,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["intencion"] == (
        "dni_consulta_estado"
    )

    assert data["verificacion"] == "ok"

    assert (
        "RENIEC" in data["respuesta"]
        or "reniec" in data["respuesta"].lower()
    )

    assert "session_id" in data
    assert data["session_id"]

    comprobar_session_id_valido(
        data["session_id"]
    )


def test_consulta_fuera_de_alcance_pasaporte():
    payload = {
        "pregunta": (
            "Necesito renovar mi pasaporte."
        )
    }

    response = client.post(
        "/api/v1/consultas",
        json=payload,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["intencion"] == "fuera_alcance"
    assert data["verificacion"] == "ok"
    assert data["fuentes"] == []

    assert "session_id" in data
    assert data["session_id"]

    comprobar_session_id_valido(
        data["session_id"]
    )


@pytest.mark.integration
def test_api_genera_sesion_si_no_se_envia():
    payload = {
        "pregunta": (
            "Quiero renovar el DNI de mi hijo menor."
        )
    }

    response = client.post(
        "/api/v1/consultas",
        json=payload,
    )

    assert response.status_code == 200

    data = response.json()

    assert "session_id" in data
    assert data["session_id"] is not None

    comprobar_session_id_valido(
        data["session_id"]
    )


@pytest.mark.integration
def test_api_reutiliza_session_id_enviado():
    session_id = (
        "12345678-1234-5678-1234-567812345678"
    )

    payload = {
        "pregunta": (
            "Quiero renovar el DNI de mi hijo menor."
        ),
        "session_id": session_id,
    }

    response = client.post(
        "/api/v1/consultas",
        json=payload,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["session_id"] == session_id
    assert data["intencion"] == (
        "dni_menor_renovacion"
    )


@pytest.mark.integration
def test_consultas_independientes_generan_sesiones_distintas():
    primera_response = client.post(
        "/api/v1/consultas",
        json={
            "pregunta": (
                "Quiero renovar el DNI de mi hijo menor."
            )
        },
    )

    segunda_response = client.post(
        "/api/v1/consultas",
        json={
            "pregunta": (
                "Mi hijo menor necesita el DNI "
                "por primera vez."
            )
        },
    )

    assert primera_response.status_code == 200
    assert segunda_response.status_code == 200

    primera_data = primera_response.json()
    segunda_data = segunda_response.json()

    assert (
        primera_data["session_id"]
        != segunda_data["session_id"]
    )

    assert primera_data["intencion"] == (
        "dni_menor_renovacion"
    )

    assert segunda_data["intencion"] == (
        "dni_menor_primera_vez"
    )


def test_rechazar_pregunta_demasiado_corta():
    response = client.post(
        "/api/v1/consultas",
        json={
            "pregunta": "ab",
        },
    )

    assert response.status_code == 422


def test_rechazar_solicitud_sin_pregunta():
    response = client.post(
        "/api/v1/consultas",
        json={},
    )

    assert response.status_code == 422


def test_endpoint_resumen_evaluacion():
    response = client.get(
        "/api/v1/evaluacion/resumen", headers={"Authorization": "Bearer test-admin-only"}
    )

    assert response.status_code == 200

    data = response.json()

    assert "total_consultas" in data
    assert "consultas_fuera_alcance" in data
    assert "consultas_observadas" in data
    assert "resumen_intenciones" in data
    assert "resumen_verificacion" in data

    assert isinstance(
        data["total_consultas"],
        int,
    )

    assert isinstance(
        data["resumen_intenciones"],
        list,
    )

    assert isinstance(
        data["resumen_verificacion"],
        list,
    )


def test_endpoint_consultas_registradas():
    response = client.get(
        "/api/v1/evaluacion/consultas?limite=5", headers={"Authorization": "Bearer test-admin-only"}
    )

    assert response.status_code == 200

    data = response.json()

    assert "total" in data
    assert "consultas" in data

    assert isinstance(
        data["total"],
        int,
    )

    assert isinstance(
        data["consultas"],
        list,
    )

    assert len(data["consultas"]) <= 5