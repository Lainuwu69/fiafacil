"""Auditoría de inicio y cierre de sesión (incluye intentos fallidos, sin guardar la contraseña)."""

from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from core.models import Auditoria


def _tienda_de(user):
    """Tienda principal del usuario (primero NEGOCIO), para que el evento aparezca en la auditoría de esa tienda."""
    membresia = user.membresias.filter(activo=True).select_related("tienda").order_by("rol").first()
    return membresia.tienda if membresia else None


@receiver(user_logged_in)
def auditar_login(sender, request, user, **kwargs):
    Auditoria.registrar(Auditoria.Evento.LOGIN, f"Inicio de sesión de {user.email}.", usuario=user,
                        tienda=_tienda_de(user), request=request)


@receiver(user_logged_out)
def auditar_logout(sender, request, user, **kwargs):
    if user is not None:
        Auditoria.registrar(Auditoria.Evento.LOGOUT, f"Cierre de sesión de {user.email}.", usuario=user,
                            tienda=_tienda_de(user), request=request)


@receiver(user_login_failed)
def auditar_login_fallido(sender, credentials, request=None, **kwargs):
    # Django ya oculta la contraseña en `credentials`; solo se guarda el correo intentado.
    email = (credentials.get("username") or "").strip().lower()
    Auditoria.registrar(
        Auditoria.Evento.LOGIN_FALLIDO, f"Intento fallido de inicio de sesión con {email or 'correo vacío'}.",
        datos={"email": email}, request=request,
    )
