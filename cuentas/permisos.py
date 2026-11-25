"""
Decoradores de permisos por rol (se validan en el servidor, no solo ocultando botones).

    @negocio_requerido     administrador del negocio con tienda ACTIVA
    @cliente_requerido     cliente con al menos una cuenta propia
    @plataforma_requerida  administrador de la plataforma (is_staff)

Un acceso sin permiso responde 403 y queda en la auditoría.
"""

from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

from core.models import Auditoria
from cuentas.models import Membresia
from tiendas.models import Tienda


def _denegar(request, motivo):
    Auditoria.registrar(
        Auditoria.Evento.ACCESO_DENEGADO,
        f"{motivo} Ruta: {request.path}"[:300],
        usuario=request.user,
        tienda=getattr(request, "tienda", None),
        request=request,
    )
    raise PermissionDenied(motivo)


def negocio_requerido(vista):
    @login_required
    @wraps(vista)
    def envoltura(request, *args, **kwargs):
        membresia = request.membresia
        if membresia is None or membresia.rol != Membresia.Rol.NEGOCIO:
            negocio = next((m for m in request.membresias if m.rol == Membresia.Rol.NEGOCIO), None)
            if negocio is None:
                _denegar(request, "Esta sección es solo para el administrador del negocio.")
            # Tiene una tienda como negocio, pero estaba trabajando como cliente: se cambia sola.
            request.session["membresia_id"] = str(negocio.pk)
            request.membresia, request.tienda = negocio, negocio.tienda
        tienda = request.tienda
        if tienda.estado == Tienda.Estado.PENDIENTE:
            return redirect("core:tienda_pendiente")
        if tienda.estado == Tienda.Estado.INACTIVA:
            messages.error(request, f"La tienda «{tienda.nombre}» fue dada de baja; sus datos se conservan solo para consulta.")
            _denegar(request, "La tienda está dada de baja.")
        return vista(request, *args, **kwargs)

    return envoltura


def cliente_requerido(vista):
    @login_required
    @wraps(vista)
    def envoltura(request, *args, **kwargs):
        tiene_cuentas = request.user.cuentas_cliente.exists()
        es_cliente = any(m.rol == Membresia.Rol.CLIENTE for m in request.membresias)
        if not (tiene_cuentas or es_cliente):
            _denegar(request, "Esta sección es solo para clientes con una cuenta.")
        return vista(request, *args, **kwargs)

    return envoltura


def plataforma_requerida(vista):
    @login_required
    @wraps(vista)
    def envoltura(request, *args, **kwargs):
        if not request.user.is_staff:
            _denegar(request, "Esta sección es solo para el administrador de la plataforma.")
        return vista(request, *args, **kwargs)

    return envoltura
