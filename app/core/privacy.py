"""Redacción parcial de identificadores; no constituye anonimización de texto libre."""
import re

from app.core.official_contacts import OFFICIAL_EMAILS, OFFICIAL_URLS

_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
_NUMERIC_ID = re.compile(r"(?<!\w)\d{8,}(?!\w)")
_LABELLED_ID = re.compile(
    r"\b(DNI|pasaporte|NIE|NIF)\s*[:#=-]?\s*"
    r"(?=[A-Z0-9]{5,20}\b)(?=[A-Z0-9]*\d)[A-Z0-9]+\b", re.I
)
_PHONE = re.compile(r"(?<!\w)\+\d[\d ()-]{7,}\d(?!\w)")


def _redactar(texto: str) -> str:
    texto = _EMAIL.sub('[CORREO REDACTADO]', texto)
    texto = _LABELLED_ID.sub(lambda m: m.group(1) + ' [IDENTIFICADOR REDACTADO]', texto)
    texto = _PHONE.sub('[TELÉFONO REDACTADO]', texto)
    return _NUMERIC_ID.sub('[IDENTIFICADOR REDACTADO]', texto)


_CONTACT = re.compile(r"https?://[^\s<>\"']+|" + _EMAIL.pattern, re.I)


def minimizar_texto(texto: str, *, permitir_oficiales: bool = False) -> str:
    if not permitir_oficiales:
        return _redactar(texto)
    parts, end = [], 0
    for match in _CONTACT.finditer(texto):
        parts.append(_redactar(texto[end:match.start()]))
        value = match.group()
        clean = value.rstrip('.,;:!?)')
        approved = clean in OFFICIAL_URLS or clean.lower() in OFFICIAL_EMAILS
        parts.append(value if approved else _redactar(value))
        end = match.end()
    parts.append(_redactar(texto[end:]))
    return ''.join(parts)
