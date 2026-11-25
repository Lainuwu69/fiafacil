from django.urls import path

from cuentas import views

app_name = "cuentas"

urlpatterns = [
    path("registro/", views.registro, name="registro"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", views.logout, name="logout"),
    path("clave/", views.CambiarClaveView.as_view(), name="cambiar_clave"),
    path("cambiar-tienda/", views.cambiar_tienda, name="cambiar_tienda"),
]
