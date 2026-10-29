"""Presentación de derivaciones; nunca autoriza reglas ni cambia la verificación."""
import re

from app.core.official_contacts import OFFICIAL_EMAILS
from app.graph.social import normalizar

# Confirmación operativa del responsable del proyecto: 29/10/2026.
# Contacto ya incluido en la lista controlada; no se obtiene del LLM ni del usuario.
CONSULAR_EMAIL = 'informes@conperturin.org'

_TARGET = r'(?:el consulado|la oficina consular|los canales oficiales del consulado|la oficina del consulado)'
_REFERRAL = re.compile(
    r'\b(?:consulte|confirme|contacte|comuniquese|escriba|consultar|confirmar|contactar|comunicarse|escribir)'
    r'\s+(?:directamente\s+)?(?:con\s+|a\s+)?' + _TARGET + r'\b'
    r'|\b(?:contacte|escriba|consulte|solicite|contactar|escribir|consultar)\s+(?:directamente\s+)?al consulado\b'
    r'|\b(?:confirme|confirmar|consulte|consultar)\s+[^.;!?\n]{1,100}?\s+con\s+' + _TARGET + r'\b'
    r'|\b(?:requiere|requieren|necesita|necesitan|pendiente de)\s+(?:la\s+)?confirmacion del consulado\b'
)
_NEGATED = re.compile(
    r'\bno\s+(?:(?:es necesario|hace falta|necesita|necesitan|debe|deben|requiere|requieren|'
    r'(?:le )?recomiendo|se recomienda)\s+(?:que\s+)?)?'
    r'(?:consult\w*|confirm\w*|contact\w*|comuni\w*|escrib\w*)[^,.;!?]*'
)


def incorporar_contacto(respuesta: str) -> str:
    """Idempotente: añade solo contacto fijo a una derivación expresa.

    Evalúa la salida final, no el texto del ciudadano. No consulta proveedores.
    El cuerpo y cualquier contacto ya presente permanecen intactos.
    """
    if CONSULAR_EMAIL.casefold() in respuesta.casefold():
        return respuesta
    texto = normalizar(respuesta)
    texto = _NEGATED.sub('', texto)
    if not _REFERRAL.search(texto):
        return respuesta
    # Defensa frente a una futura retirada del contacto de la lista aprobada.
    if CONSULAR_EMAIL not in OFFICIAL_EMAILS:
        return respuesta
    return (respuesta + '\n\nPara recibir orientación, puede escribir al Consulado General del Perú en Turín: '
            f'[**{CONSULAR_EMAIL}**](mailto:{CONSULAR_EMAIL}).\n\n'
            'Le recomiendo explicar brevemente el trámite que desea realizar para que la oficina consular '
            'pueda indicarle los requisitos correspondientes.')
