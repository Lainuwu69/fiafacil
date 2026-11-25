from django.urls import path

from creditos import views

app_name = "creditos"

urlpatterns = [
    path("ventas/nueva/", views.nueva_venta, name="nueva_venta"),
    path("compras/", views.compras, name="compras"),
    path("compras/simular/", views.api_simular, name="api_simular"),
    path("compras/<uuid:compra_id>/", views.compra, name="compra"),
    path("compras/<uuid:compra_id>/anular/", views.anular_compra, name="anular_compra"),
    path("pagos/<uuid:pago_id>/anular/", views.anular_pago, name="anular_pago"),
    path("estados/", views.estados, name="estados"),
    path("clientes/<uuid:cuenta_id>/ciclo/<str:corte>/", views.ciclo, name="ciclo"),
    path("clientes/<uuid:cuenta_id>/pago/", views.pago, name="pago"),
    path("clientes/<uuid:cuenta_id>/pago/calcular/", views.api_calcular_pago, name="api_calcular_pago"),
    path("pagos/", views.pagos, name="pagos"),
    path("pagos/<uuid:pago_id>/", views.comprobante, name="comprobante"),
]
