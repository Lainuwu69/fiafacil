"""Vistas de tiendas: plataforma (alta y baja de tiendas) y catálogo del negocio."""

from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.accesos import de_mi_tienda
from core.models import Auditoria
from cuentas.permisos import negocio_requerido, plataforma_requerida
from tiendas.forms import ArticuloForm
from tiendas.models import Articulo, Tienda


# ---------------------------------------------------------------------------
# Catálogo del negocio (requisito 2)
# ---------------------------------------------------------------------------

@negocio_requerido
def catalogo(request):
    ver = request.GET.get("ver", "activos")
    articulos = Articulo.objects.filter(tienda=request.tienda)
    if ver == "activos":
        articulos = articulos.filter(activo=True)
    elif ver == "baja":
        articulos = articulos.filter(activo=False)
    q = request.GET.get("q", "").strip()
    if q:
        articulos = articulos.filter(Q(descripcion__icontains=q) | Q(marca__icontains=q) | Q(proveedor__icontains=q))
    return render(request, "tiendas/catalogo.html", {"articulos": articulos.order_by("descripcion"), "ver": ver, "q": q})


@negocio_requerido
def articulo_form(request, articulo_id=None):
    articulo = de_mi_tienda(request, Articulo, articulo_id) if articulo_id else None
    form = ArticuloForm(request.POST or None, request.FILES or None, instance=articulo)
    if request.method == "POST" and form.is_valid():
        nuevo = articulo is None
        obj = form.save(commit=False)
        obj.tienda = request.tienda
        obj.save()
        Auditoria.registrar(
            Auditoria.Evento.ALTA if nuevo else Auditoria.Evento.MODIFICACION,
            f"{'Alta' if nuevo else 'Modificación'} del artículo «{obj}» (contado {obj.precio_contado}, lista {obj.precio_credito}).",
            usuario=request.user, tienda=request.tienda, objeto=obj, request=request,
        )
        messages.success(request, f"Artículo «{obj}» {'registrado' if nuevo else 'actualizado'}.")
        return redirect("tiendas:catalogo")
    return render(request, "tiendas/articulo_form.html", {"form": form, "articulo": articulo})


@negocio_requerido
@require_POST
def articulo_estado(request, articulo_id):
    """Baja lógica o reactivación del artículo (RN09): las ventas pasadas lo conservan."""
    articulo = de_mi_tienda(request, Articulo, articulo_id)
    articulo.activo = not articulo.activo
    articulo.save(update_fields=["activo"])
    accion = "reactivado" if articulo.activo else "dado de baja"
    Auditoria.registrar(Auditoria.Evento.ALTA if articulo.activo else Auditoria.Evento.BAJA, f"Artículo «{articulo}» {accion}.",
                        usuario=request.user, tienda=request.tienda, objeto=articulo, request=request)
    messages.success(request, f"Artículo «{articulo}» {accion}.")
    return redirect("tiendas:catalogo")


# ---------------------------------------------------------------------------
# Plataforma (requisito 1)
# ---------------------------------------------------------------------------

ACCIONES = {
    # acción: (estados desde los que se permite, estado final, evento de auditoría, verbo para el mensaje)
    "activar": ({Tienda.Estado.PENDIENTE}, Tienda.Estado.ACTIVA, Auditoria.Evento.ACTIVACION, "activada"),
    "baja": ({Tienda.Estado.PENDIENTE, Tienda.Estado.ACTIVA}, Tienda.Estado.INACTIVA, Auditoria.Evento.BAJA, "dada de baja"),
    "reactivar": ({Tienda.Estado.INACTIVA}, Tienda.Estado.ACTIVA, Auditoria.Evento.ACTIVACION, "reactivada"),
}


@plataforma_requerida
def plataforma(request):
    filtro = request.GET.get("estado", "")
    tiendas = Tienda.objects.annotate(
        n_clientes=Count("cuentas", distinct=True),
        n_usuarios=Count("membresias", filter=Q(membresias__rol="NEGOCIO"), distinct=True),
    ).prefetch_related("membresias__usuario")
    if filtro in Tienda.Estado.values:
        tiendas = tiendas.filter(estado=filtro)
    conteo = {e: Tienda.objects.filter(estado=e).count() for e in Tienda.Estado.values}
    return render(request, "tiendas/plataforma.html", {
        "tiendas": tiendas.order_by("estado", "codigo"), "filtro": filtro, "conteo": conteo, "estados": Tienda.Estado,
    })


@plataforma_requerida
@require_POST
def cambiar_estado(request, tienda_id, accion):
    if accion not in ACCIONES:
        return redirect("tiendas:plataforma")
    desde, hacia, evento, verbo = ACCIONES[accion]
    tienda = get_object_or_404(Tienda, pk=tienda_id)
    if tienda.estado not in desde:
        messages.warning(request, f"La tienda {tienda.codigo} está {tienda.get_estado_display().lower()}; no se puede {accion}.")
        return redirect("tiendas:plataforma")
    tienda.estado = hacia
    if hacia == Tienda.Estado.ACTIVA:
        tienda.fecha_activacion, tienda.fecha_baja = timezone.now(), None
    else:
        tienda.fecha_baja = timezone.now()
    tienda.save(update_fields=["estado", "fecha_activacion", "fecha_baja"])
    Auditoria.registrar(evento, f"Tienda {tienda.codigo} «{tienda.nombre}» {verbo} por la plataforma.",
                        usuario=request.user, tienda=tienda, objeto=tienda, request=request)
    messages.success(request, f"Tienda {tienda.codigo} «{tienda.nombre}» {verbo}.")
    return redirect("tiendas:plataforma")
