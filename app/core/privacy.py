"""Redacción parcial de identificadores; no constituye anonimización de texto libre."""
import re

_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
_NUMERIC_ID = re.compile(r"(?<!\w)\d{8,}(?!\w)")
_LABELLED_ID = re.compile(
    r"\b(DNI|pasaporte|NIE|NIF)\s*[:#=-]?\s*"
    r"(?=[A-Z0-9]{5,20}\b)(?=[A-Z0-9]*\d)[A-Z0-9]+\b", re.I
)
_PHONE = re.compile(r"(?<!\w)\+\d[\d ()-]{7,}\d(?!\w)")


def minimizar_texto(texto: str) -> str:
    texto = _EMAIL.sub('[CORREO REDACTADO]', texto)
    texto = _LABELLED_ID.sub(lambda m: m.group(1) + ' [IDENTIFICADOR REDACTADO]', texto)
    texto = _PHONE.sub('[TELÉFONO REDACTADO]', texto)
    return _NUMERIC_ID.sub('[IDENTIFICADOR REDACTADO]', texto)
