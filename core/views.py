"""Vistas generales: inicio según el rol, panel del negocio, auditoría y aviso de tienda pendiente.

El portal del cliente está en core/portal.py.
"""

from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import redirect, render
from django.utils import timezone

from core.models import Auditoria
from creditos import servicios as s
from creditos.models import Obligacion
from cuentas.models import Membresia
from cuentas.permisos import negocio_requerido
from tiendas.models import Tienda


def inicio(request):
    """Envía a cada perfil a su pantalla principal."""
    if not request.user.is_authenticated:
        return redirect("cuentas:login")
    if request.membresia and request.membresia.rol == Membresia.Rol.NEGOCIO:
        if request.tienda.estado == Tienda.Estado.PENDIENTE:
            return redirect("core:tienda_pendiente")
        return redirect("core:panel")
    if request.user.is_staff:
        return redirect("tiendas:plataforma")
    if request.user.cuentas_cliente.exists() or (request.membresia and request.membresia.rol == Membresia.Rol.CLIENTE):
        return redirect("core:portal")
    return render(request, "core/sin_permisos.html")


def ayuda(request):
    """Ayuda general (punto 9d): guía por perfil, preguntas frecuentes, fórmulas y soporte.

    Es pública para que también la consulte quien todavía no se registra.
    """
    return render(request, "core/ayuda.html", {"base": "base.html" if request.user.is_authenticated else "base_auth.html"})


@login_required
def tienda_pendiente(request):
    return render(request, "core/tienda_pendiente.html")


@negocio_requerido
def panel(request):
    """Panel del negocio: indicadores de cartera, flujo de caja proyectado y vencimientos."""
    hoy = timezone.localdate()
    indicadores = s.indicadores_cartera(request.tienda, hoy)
    flujo = s.flujo_cobranzas(request.tienda, hoy, meses=6)
    for filas in flujo.values():  # ancho de las barras del gráfico (proporción del mes con más cobros)
        maximo = max((f["total"] for f in filas), default=0) or 1
        for f in filas:
            f["ancho"] = int(f["total"] / maximo * 100)
    pendientes = Obligacion.objects.filter(tienda=request.tienda, estado=Obligacion.Estado.PENDIENTE).select_related("cuenta", "compra")
    return render(request, "core/panel.html", {
        "hoy": hoy,
        "indicadores": indicadores,
        "flujo": flujo,
        "proximos": pendientes.filter(vencimiento__gte=hoy, vencimiento__lte=hoy + timedelta(days=15)).order_by("vencimiento")[:15],
        "vencidas": pendientes.filter(vencimiento__lt=hoy).order_by("vencimiento")[:15],
        "estados_pendientes": s.cortes_pendientes_de_estado(request.tienda),
    })


@negocio_requerido
def auditoria(request):
    """Bitácora de la tienda: quién hizo qué y cuándo (solo lectura)."""
    evento = request.GET.get("evento", "")
    qs = Auditoria.objects.filter(tienda=request.tienda).select_related("usuario")
    if evento in Auditoria.Evento.values:
        qs = qs.filter(evento=evento)
    return render(request, "core/auditoria.html", {
        "pagina": Paginator(qs.order_by("-instante"), 50).get_page(request.GET.get("p")),
        "eventos": Auditoria.Evento.choices, "evento": evento,
        "filtro_qs": f"evento={evento}" if evento else "",
    })
