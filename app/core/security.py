from secrets import compare_digest

from fastapi import Header, HTTPException, Response

from app.core.config import settings


def exigir_admin(response: Response, authorization: str | None = Header(default=None)) -> None:
    expected = settings.internal_api_token
    if expected is None or not expected.get_secret_value():
        raise HTTPException(503, 'Acceso interno deshabilitado')
    supplied = authorization.removeprefix('Bearer ') if authorization else ''
    if not authorization or not authorization.startswith('Bearer ') or not compare_digest(
        supplied.encode(), expected.get_secret_value().encode()
    ):
        raise HTTPException(401, 'Credenciales internas inválidas', headers={'WWW-Authenticate': 'Bearer'})

    response.headers["Cache-Control"] = "no-store"
    response.headers["Vary"] = "Authorization"
