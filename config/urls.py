"""
Rutas principales de FíaFácil.

Cada app agrega sus rutas en las fases siguientes (cuentas, tiendas, clientes,
creditos y core).
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "FíaFácil · Administración"
admin.site.site_title = "FíaFácil"
admin.site.index_title = "Registro central"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("cuentas/", include("cuentas.urls")),
    path("tiendas/", include("tiendas.urls")),
    path("clientes/", include("clientes.urls")),
    path("", include("creditos.urls")),
    path("", include("core.urls")),
]

# En desarrollo Django sirve las imágenes subidas (catálogo).
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
