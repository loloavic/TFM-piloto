"""Lista controlada por revisión de código, no por entradas ni respuestas LLM.

Procedencia: data/raw/dni_consulta_estado.txt, dni_menor_primera_vez.txt
 y dni_menor_renovacion.txt. Cambiar solo tras revisar la documentación aprobada.
"""
OFFICIAL_EMAILS = frozenset({'informes@conperturin.org'})
OFFICIAL_URLS = frozenset({
    'https://serviciosportal.reniec.gob.pe/cetdnipi/inicio.htm',
    'https://bookeo.com/cturin?type=223Y6PNNP174468CBDCD&option_TYPE_OF_SERVICE=YMRKCTKN',
    'https://www.consulado.pe/es/turin/Paginas/Retiro-de-Documentos.aspx#dni',
    'https://www.consulado.pe/es/turin/tramite/Paginas/DNI/Menor-inscripcion.aspx',
    'https://www.consulado.pe/es/turin/tramite/Paginas/DNI/Menor-renovacion.aspx',
})
