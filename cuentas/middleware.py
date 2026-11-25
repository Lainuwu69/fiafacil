"""
TiendaActivaMiddleware: en cada solicitud determina con qué tienda trabaja el usuario.

Deja disponibles:
- request.membresias: permisos activos del usuario (una por tienda y rol).
- request.membresia: la membresía elegida (guardada en la sesión).
- request.tienda: la tienda de esa membresía.

Todas las vistas del negocio filtran sus datos por request.tienda (RN01). Como
la tienda sale de la membresía del usuario autenticado y no de un dato enviado
por el navegador, un usuario no puede "pedir" otra tienda cambiando la URL.
"""

from cuentas.models import Membresia

CLAVE_SESION = "membresia_id"


class TiendaActivaMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.membresias, request.membresia, request.tienda = [], None, None
        if request.user.is_authenticated:
            membresias = list(
                Membresia.objects.filter(usuario=request.user, activo=True)
                .select_related("tienda")
                .order_by("rol", "tienda__nombre")  # NEGOCIO antes que CLIENTE
            )
            request.membresias = membresias
            elegida_id = request.session.get(CLAVE_SESION)
            elegida = next((m for m in membresias if str(m.pk) == elegida_id), None)
            if elegida is None and membresias:
                elegida = membresias[0]
                request.session[CLAVE_SESION] = str(elegida.pk)
            if elegida is not None:
                request.membresia, request.tienda = elegida, elegida.tienda
        return self.get_response(request)
