"""Datos disponibles en todas las plantillas (procesador de contexto)."""

from django.conf import settings


def fiafacil(request):
    usuario = getattr(request, "user", None)
    es_cliente = False
    if usuario is not None and usuario.is_authenticated:
        es_cliente = usuario.cuentas_cliente.filter(activo=True).exists() or any(
            m.rol == "CLIENTE" for m in getattr(request, "membresias", [])
        )
    return {
        "soporte_whatsapp": settings.SOPORTE_WHATSAPP,
        "soporte_correo": settings.SOPORTE_CORREO,
        "es_cliente": es_cliente,
    }
