"""Operaciones de cuentas de usuario que escriben datos (en una transacción y auditadas)."""

from django.contrib.auth import get_user_model
from django.db import transaction

from core.models import Auditoria
from cuentas.models import Membresia
from tiendas.models import Tienda


def registrar_negocio(datos, request=None):
    """Registro público: crea el usuario, su tienda en estado PENDIENTE y la membresía NEGOCIO.

    La tienda no puede vender hasta que el administrador de la plataforma la active
    (requisito 1 del enunciado: el administrador del sistema da de alta a la tienda).
    """
    with transaction.atomic():
        usuario = get_user_model().objects.create_user(
            datos["email"], datos["password1"], nombres=datos["nombres"], apellidos=datos.get("apellidos", "")
        )
        tienda = Tienda.objects.create(
            nombre=datos["nombre_tienda"], giro=datos["giro"], ruc=datos.get("ruc"),
            direccion=datos["direccion"], telefono=datos.get("telefono", ""), estado=Tienda.Estado.PENDIENTE,
        )
        Membresia.objects.create(usuario=usuario, tienda=tienda, rol=Membresia.Rol.NEGOCIO)
        Auditoria.registrar(
            Auditoria.Evento.REGISTRO,
            f"Registro de {usuario.email} con la tienda {tienda.codigo} «{tienda.nombre}» (pendiente de activación).",
            usuario=usuario, tienda=tienda, objeto=tienda, request=request,
        )
    return usuario, tienda
