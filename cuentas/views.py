"""Vistas de registro, inicio y cierre de sesión, y cambio de tienda activa."""

from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST

from core.models import Auditoria
from cuentas.forms import CambioClaveForm, LoginForm, RegistroForm
from cuentas.middleware import CLAVE_SESION
from cuentas.servicios import registrar_negocio


def registro(request):
    """Registro público de un negocio. No inicia sesión automáticamente: el usuario debe
    ingresar con su correo y contraseña (así se demuestra el login en la exposición)."""
    if request.user.is_authenticated:
        return redirect("core:inicio")
    form = RegistroForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        usuario, tienda = registrar_negocio(form.cleaned_data, request)
        messages.success(
            request,
            f"¡Listo! Creamos tu usuario {usuario.email} y la tienda {tienda.codigo} «{tienda.nombre}». "
            "Ya puedes iniciar sesión; podrás vender cuando la plataforma active tu tienda.",
        )
        return redirect("cuentas:login")
    return render(request, "cuentas/registro.html", {"form": form})


class LoginView(auth_views.LoginView):
    template_name = "cuentas/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


class CambiarClaveView(auth_views.PasswordChangeView):
    """Cualquier usuario cambia su contraseña. La sesión sigue abierta y el cambio se audita."""

    template_name = "cuentas/cambiar_clave.html"
    form_class = CambioClaveForm
    success_url = reverse_lazy("core:inicio")

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        Auditoria.registrar(Auditoria.Evento.CAMBIO_CLAVE, f"{self.request.user.email} cambió su contraseña.",
                            usuario=self.request.user, tienda=getattr(self.request, "tienda", None), request=self.request)
        messages.success(self.request, "Tu contraseña se cambió correctamente.")
        return respuesta


@require_POST
def logout(request):
    return auth_views.LogoutView.as_view()(request)


@login_required
@require_POST
def cambiar_tienda(request):
    """Cambia la tienda con la que se trabaja. Solo acepta membresías del propio usuario."""
    elegida = request.POST.get("membresia")
    if any(str(m.pk) == elegida for m in request.membresias):
        request.session[CLAVE_SESION] = elegida
    else:
        messages.error(request, "No tienes permisos en esa tienda.")
    return redirect("core:inicio")
