"""
Portal del cliente (requisito 1: "el cliente solo consulta").

Todas las consultas se filtran por el usuario que inició sesión
(CuentaCliente.usuario = request.user). Un cliente nunca ve cuentas de otros:
si cambia un identificador en la URL, recibe 404 y el intento queda auditado.
Solo hay vistas GET: el cliente no puede registrar ni modificar nada.
"""

from datetime import datetime

from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import render
from django.utils import timezone

from clientes.models import CuentaCliente
from core.models import Auditoria
from creditos import servicios as s
from creditos.models import Compra, Obligacion, Pago
from cuentas.permisos import cliente_requerido

FORMATO_CORTE = "%Y%m%d%H%M%S"


def _mio(request, modelo, pk, ruta_usuario):
    """Registro del modelo que pertenece al cliente; si no, audita y responde 404."""
    try:
        return modelo.objects.select_related().get(pk=pk, **{ruta_usuario: request.user})
    except (modelo.DoesNotExist, ValidationError, ValueError):
        Auditoria.registrar(
            Auditoria.Evento.ACCESO_DENEGADO,
            f"Un cliente intentó ver {modelo._meta.verbose_name} {pk} que no es suyo.",
            usuario=request.user, datos={"modelo": modelo.__name__, "id": str(pk)}, request=request,
        )
        raise Http404("No encontrado.")


@cliente_requerido
def inicio(request):
    hoy = timezone.localdate()
    tarjetas = []
    for cuenta in request.user.cuentas_cliente.select_related("tienda").order_by("tienda__nombre", "codigo"):
        pendientes = list(cuenta.obligaciones.filter(estado=Obligacion.Estado.PENDIENTE).order_by("vencimiento"))
        vencidas = [o for o in pendientes if o.vencimiento < hoy]
        proxima = next((o for o in pendientes if o.vencimiento >= hoy), None)
        tarjetas.append({
            "cuenta": cuenta,
            "condicion": cuenta.condicion_vigente(),
            "deuda": sum((o.total for o in pendientes), 0),
            "disponible": s.disponible(cuenta),
            "vencido": sum((o.total for o in vencidas), 0),
            "proxima": proxima,
            "monto_proximo": sum((o.total for o in pendientes if proxima and o.vencimiento == proxima.vencimiento), 0),
        })
    return render(request, "portal/inicio.html", {"tarjetas": tarjetas, "hoy": hoy})


@cliente_requerido
def cuenta(request, cuenta_id):
    c = _mio(request, CuentaCliente, cuenta_id, "usuario")
    vigente = c.condicion_vigente()
    pendientes = list(c.obligaciones.filter(estado=Obligacion.Estado.PENDIENTE).select_related("compra").order_by("vencimiento", "numero"))
    return render(request, "portal/cuenta.html", {
        "cuenta": c, "vigente": vigente, "hoy": timezone.localdate(), "ahora": timezone.now(),
        "tem": s.tasa_compensatoria(vigente).tem() if vigente else None,
        "tea": s.tasa_compensatoria(vigente).tea() if vigente else None,
        "pendientes": pendientes, "deuda": sum((o.total for o in pendientes), 0),
        "exposicion": s.exposicion(c), "disponible": s.disponible(c, vigente),
        "compras": Compra.objects.filter(cuenta=c).order_by("-fecha_compra"),
        "pagos": Pago.objects.filter(cuenta=c).order_by("-fecha_efectiva", "-numero"),
        "cortes": [{"corte": k, "estado": c.estados.filter(corte=k).first()} for k in s.cortes_de_cuenta(c)],
    })


@cliente_requerido
def compra(request, compra_id):
    obj = _mio(request, Compra, compra_id, "cuenta__usuario")
    return render(request, "portal/compra.html", {
        "compra": obj, "detalles": obj.detalles.order_by("linea"), "obligaciones": obj.obligaciones.order_by("numero"),
        "m": obj.moneda,
    })


@cliente_requerido
def ciclo(request, cuenta_id, corte):
    c = _mio(request, CuentaCliente, cuenta_id, "usuario")
    try:
        corte_dt = timezone.make_aware(datetime.strptime(corte, FORMATO_CORTE))
    except ValueError:
        raise Http404("Corte inválido.")
    r = s.resumen_ciclo(c, corte_dt, timezone.localdate())
    if not r["lineas"]:
        raise Http404("No hay obligaciones en ese ciclo.")
    return render(request, "portal/ciclo.html", {"cuenta": c, "r": r, "m": c.moneda, "ahora": timezone.now()})


@cliente_requerido
def comprobante(request, pago_id):
    p = _mio(request, Pago, pago_id, "cuenta__usuario")
    return render(request, "portal/comprobante.html", {
        "pago": p, "aplicaciones": p.aplicaciones.select_related("obligacion__compra").order_by("obligacion__vencimiento"),
    })
