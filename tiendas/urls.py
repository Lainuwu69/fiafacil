from django.urls import path

from tiendas import views

app_name = "tiendas"

urlpatterns = [
    path("plataforma/", views.plataforma, name="plataforma"),
    path("plataforma/<uuid:tienda_id>/<str:accion>/", views.cambiar_estado, name="cambiar_estado"),
    path("catalogo/", views.catalogo, name="catalogo"),
    path("catalogo/nuevo/", views.articulo_form, name="articulo_nuevo"),
    path("catalogo/<uuid:articulo_id>/editar/", views.articulo_form, name="articulo_editar"),
    path("catalogo/<uuid:articulo_id>/estado/", views.articulo_estado, name="articulo_estado"),
]
