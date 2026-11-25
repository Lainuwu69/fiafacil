from django.urls import path

from core import portal, views

app_name = "core"

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("panel/", views.panel, name="panel"),
    path("auditoria/", views.auditoria, name="auditoria"),
    path("ayuda/", views.ayuda, name="ayuda"),
    path("tienda-pendiente/", views.tienda_pendiente, name="tienda_pendiente"),
    # Portal del cliente (solo consulta)
    path("portal/", portal.inicio, name="portal"),
    path("portal/cuentas/<uuid:cuenta_id>/", portal.cuenta, name="portal_cuenta"),
    path("portal/cuentas/<uuid:cuenta_id>/ciclo/<str:corte>/", portal.ciclo, name="portal_ciclo"),
    path("portal/compras/<uuid:compra_id>/", portal.compra, name="portal_compra"),
    path("portal/comprobantes/<uuid:pago_id>/", portal.comprobante, name="portal_comprobante"),
]
