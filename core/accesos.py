"""Búsqueda de registros limitada a la tienda del usuario (RN01).

Si el registro no existe o es de otra tienda, se audita el intento y se responde 404
("no encontrado"), sin revelar que el registro existe en otra tienda.
"""

from django.core.exceptions import ValidationError
from django.http import Http404

from core.models import Auditoria


def de_mi_tienda(request, modelo, pk, campo_tienda="tienda", **filtros):
    try:
        return modelo.objects.get(pk=pk, **{campo_tienda: request.tienda}, **filtros)
    except (modelo.DoesNotExist, ValidationError, ValueError):
        Auditoria.registrar(
            Auditoria.Evento.ACCESO_DENEGADO,
            f"Intento de acceder a {modelo._meta.verbose_name} {pk} fuera de la tienda {request.tienda.codigo}.",
            usuario=request.user, tienda=request.tienda, datos={"modelo": modelo.__name__, "id": str(pk)}, request=request,
        )
        raise Http404(f"{modelo._meta.verbose_name.capitalize()} no encontrado en esta tienda.")
