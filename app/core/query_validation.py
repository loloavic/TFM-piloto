"""Validación léxica compartida; no autoriza sesiones ni confirma hechos."""
import unicodedata

ERROR_CONSULTA = 'Ingrese una consulta de 3 a 1000 caracteres o una respuesta breve válida: sí, si o no.'


def validar_consulta(texto: str) -> str:
    clean = texto.strip()
    normalized = ''.join(c for c in unicodedata.normalize('NFD', clean.casefold())
                         if unicodedata.category(c) != 'Mn')
    if len(texto) > 1000 or not clean or not any(c.isalnum() for c in clean):
        raise ValueError(ERROR_CONSULTA)
    if len(clean) < 3 and normalized not in {'si', 'no'}:
        raise ValueError(ERROR_CONSULTA)
    return clean
