"""Operaciones sobre clientes: abrir una cuenta con sus condiciones y darle acceso al portal."""

from django.contrib.auth import get_user_model
from django.db import transaction

from clientes.models import CuentaCliente
from core.models import Auditoria
from creditos.servicios import ErrorNegocio, guardar_condicion
from cuentas.models import Membresia

Usuario = get_user_model()


def abrir_cuenta(tienda, usuario, datos_cuenta, datos_condicion, vigente_desde=None, request=None):
    """Crea la cuenta del cliente y la versión 1 de sus condiciones en una sola transacción."""
    with transaction.atomic():
        cuenta = CuentaCliente.objects.create(tienda=tienda, **datos_cuenta)
        guardar_condicion(cuenta, usuario, datos_condicion, vigente_desde=vigente_desde, request=request)
        Auditoria.registrar(
            Auditoria.Evento.ALTA, f"Alta del cliente {cuenta.codigo} {cuenta.nombre} ({cuenta.moneda}).",
            usuario=usuario, tienda=tienda, objeto=cuenta, request=request,
        )
    return cuenta


def dar_acceso_cliente(cuenta, email, password, usuario, request=None):
    """Vincula la cuenta a un usuario CLIENTE (lo crea si no existe) para que consulte en el portal.

    Si el correo ya tiene usuario (por ejemplo, es cliente de otra tienda), se reutiliza y no
    se cambia su contraseña.
    """
    email = email.strip().lower()
    with transaction.atomic():
        cliente = Usuario.objects.filter(email__iexact=email).first()
        creado = cliente is None
        if creado:
            if not password:
                raise ErrorNegocio("Escribe una contraseña inicial para el cliente.")
            nombres = cuenta.nombre.split(" ", 1)
            cliente = Usuario.objects.create_user(email, password, nombres=nombres[0], apellidos=nombres[1] if len(nombres) > 1 else "")
        if cuenta.usuario_id and cuenta.usuario_id != cliente.pk:
            raise ErrorNegocio(f"La cuenta {cuenta.codigo} ya está vinculada a otro usuario ({cuenta.usuario.email}).")
        cuenta.usuario = cliente
        cuenta.save(update_fields=["usuario"])
        membresia, _ = Membresia.objects.get_or_create(usuario=cliente, tienda=cuenta.tienda, rol=Membresia.Rol.CLIENTE)
        if not membresia.activo:
            membresia.activo = True
            membresia.save(update_fields=["activo"])
        Auditoria.registrar(
            Auditoria.Evento.ALTA,
            f"Acceso al portal para {cuenta.codigo} con el usuario {cliente.email}{' (nuevo)' if creado else ' (existente)'}.",
            usuario=usuario, tienda=cuenta.tienda, objeto=cuenta, request=request,
        )
    return cliente, creado
