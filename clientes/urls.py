from django.urls import path

from clientes import views

app_name = "clientes"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("nuevo/", views.nuevo, name="nuevo"),
    path("api/tasa-equivalente/", views.api_tasa_equivalente, name="api_tasa"),
    path("<uuid:cuenta_id>/", views.detalle, name="detalle"),
    path("<uuid:cuenta_id>/editar/", views.editar, name="editar"),
    path("<uuid:cuenta_id>/condicion/", views.condicion, name="condicion"),
    path("<uuid:cuenta_id>/estado/", views.cambiar_estado, name="estado"),
    path("<uuid:cuenta_id>/acceso/", views.acceso, name="acceso"),
]
