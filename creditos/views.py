"""
Pantallas y API JSON del proceso financiero (requisitos 4, 5 y 6).

- Nueva venta: el navegador envía las líneas a /compras/simular/ y muestra lo que
  calcula el servidor (ciclo, vencimiento, días, tasa, interés o cronograma,
  disponible, TCEA y alternativas). Al confirmar, se registra con una clave de
  idempotencia (un doble clic no duplica la venta).
- Estados de cuenta: vista previa del ciclo y generación una vez cumplido el corte.
- Pagos: /clientes/<id>/pago/calcular/ liquida mora → interés → capital; el importe
  recibido debe ser exacto.
"""

import json
import uuid
from datetime import date, datetime

from django.contrib import messages
from django.core.paginator import Paginator
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from clientes.models import CuentaCliente
from core.accesos import de_mi_tienda
from core.constantes import SIMBOLO_MONEDA, Modalidad
from creditos import finanzas as fin
from creditos import servicios as s
from creditos.models import Compra, EstadoCuenta, Obligacion, Pago
from cuentas.permisos import negocio_requerido
from tiendas.models import Articulo

FORMATO_CORTE = "%Y%m%d%H%M%S"


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def _fecha_hora(texto):
    """'2026-09-15T10:00' (input datetime-local, hora de Lima) → datetime con zona."""
    if not texto:
        return None
    try:
        valor = datetime.fromisoformat(str(texto).strip())
    except ValueError:
        return None
    return timezone.make_aware(valor) if timezone.is_naive(valor) else valor


def _fecha(texto):
    try:
        return date.fromisoformat(str(texto).strip())
    except (TypeError, ValueError):
        return None


def _t(valor):
    return None if valor is None else str(valor)


def _local(dt, formato="%d/%m/%Y %H:%M"):
    return timezone.localtime(dt).strftime(formato)


def _lineas_desde_post(post):
    return [{"articulo_id": a, "cantidad": c} for a, c in zip(post.getlist("articulo"), post.getlist("cantidad")) if a or c]


def simulacion_a_json(sim):
    """Convierte la simulación del servidor a JSON (importes como texto para no perder decimales)."""
    moneda = sim.cuenta.moneda
    datos = {
        "valida": sim.valida, "errores": sim.errores, "moneda": moneda, "simbolo": SIMBOLO_MONEDA.get(moneda, moneda),
        "modalidad": sim.modalidad,
        "lineas": [{"descripcion": ln.articulo.descripcion, "cantidad": _t(ln.cantidad), "precio": _t(ln.precio_unitario),
                    "importe": _t(ln.importe)} for ln in sim.lineas],
        "capital": _t(sim.capital), "capital_contado": _t(sim.capital_contado),
        "limite": _t(sim.limite), "exposicion_actual": _t(sim.exposicion_actual),
        "nueva_exposicion": _t(sim.nueva_exposicion),
        "disponible_antes": _t(sim.disponible_antes), "disponible_despues": _t(sim.disponible_despues),
        "condicion": sim.condicion.version if sim.condicion else None,
    }
    if sim.ciclo:
        datos.update({"corte": _local(sim.ciclo.corte), "fecha_pago": sim.ciclo.fecha_pago.strftime("%d/%m/%Y")})
    if sim.mensual:
        m = sim.mensual
        datos["mensual"] = {"dias": m.dias, "tasa": fin.formato_tasa(m.tasa_periodo), "interes": _t(m.interes), "total": _t(m.total)}
    if sim.cuotas:
        c = sim.cuotas
        datos["cuotas"] = {
            "dias_gracia": c.dias_gracia, "tem": fin.formato_tasa(c.tem), "capital_con_gracia": _t(c.capital_con_gracia),
            "interes_gracia": _t(c.interes_gracia), "cuota": _t(c.cuota), "total": _t(c.total_pagado),
            "interes_total": _t(c.interes_total),
            "filas": [{"numero": f.numero, "vencimiento": f.vencimiento.strftime("%d/%m/%Y"), "saldo_inicial": _t(f.saldo_inicial),
                       "interes": _t(f.interes), "cuota": _t(f.cuota), "amortizacion": _t(f.amortizacion),
                       "saldo_final": _t(f.saldo_final)} for f in c.filas],
        }
    if sim.tcea is not None:
        datos["tcea"] = fin.formato_tasa(sim.tcea)
        datos["tcea_contado"] = fin.formato_tasa(sim.tcea_contado)
    datos["alternativas"] = [
        {"nombre": a.nombre, "total": _t(a.total), "cuota": _t(a.cuota), "costo": _t(a.costo_financiero),
         "tcea": fin.formato_tasa(a.tcea, 2) if a.tcea is not None else None,
         "primer_pago": a.primer_pago.strftime("%d/%m/%Y") if a.primer_pago else None}
        for a in sim.alternativas
    ]
    return datos


# ---------------------------------------------------------------------------
# Ventas
# ---------------------------------------------------------------------------

@negocio_requerido
def nueva_venta(request):
    tienda = request.tienda
    cuentas = CuentaCliente.objects.filter(tienda=tienda, activo=True).order_by("nombre")
    articulos = Articulo.objects.filter(tienda=tienda, activo=True).order_by("descripcion")
    contexto = {
        "cuentas": cuentas, "articulos": articulos, "modalidades": Modalidad.choices,
        "ahora": timezone.localtime().strftime("%Y-%m-%dT%H:%M"),
        "clave": request.POST.get("clave") or str(uuid.uuid4()),
        "cuenta_id": request.POST.get("cuenta") or request.GET.get("cuenta", ""),
        "lineas": _lineas_desde_post(request.POST) if request.method == "POST" else [],
        "fecha": request.POST.get("fecha_compra", ""), "modalidad": request.POST.get("modalidad", Modalidad.MENSUAL),
        "n_cuotas": request.POST.get("n_cuotas", ""),
    }
    if request.method == "POST":
        try:
            clave = uuid.UUID(request.POST.get("clave", ""))
        except ValueError:
            clave = uuid.uuid4()
        try:
            if not request.POST.get("cuenta"):
                raise s.ErrorNegocio("Elige el cliente que compra.")
            compra = s.registrar_compra(
                request.user, tienda, request.POST.get("cuenta"), _lineas_desde_post(request.POST),
                request.POST.get("modalidad"), request.POST.get("n_cuotas") or None,
                _fecha_hora(request.POST.get("fecha_compra")), clave, request=request,
            )
        except s.ErrorNegocio as e:
            for error in e.datos.get("errores", [e.mensaje]):
                messages.error(request, error)
        else:
            messages.success(request, f"Venta N° {compra.numero} registrada para {compra.cuenta.nombre}.")
            return redirect("creditos:compra", compra_id=compra.pk)
    return render(request, "creditos/venta.html", contexto)


@negocio_requerido
@require_POST
def api_simular(request):
    """Simula la compra en el servidor y devuelve el resultado en JSON (no graba nada)."""
    try:
        d = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"valida": False, "errores": ["Solicitud inválida."]}, status=400)
    if not d.get("cuenta"):
        return JsonResponse({"valida": False, "errores": ["Elige el cliente que compra."]})
    try:
        cuenta = s.obtener_cuenta(request.tienda, d.get("cuenta"), request.user, request)
    except Http404:
        return JsonResponse({"valida": False, "errores": ["Elige un cliente de tu tienda."]})
    lineas = [ln for ln in d.get("lineas", []) if ln.get("articulo_id") or ln.get("cantidad")]
    try:
        sim = s.calcular_compra(cuenta, lineas, d.get("modalidad"), d.get("n_cuotas") or None, _fecha_hora(d.get("fecha_compra")))
    except s.ErrorNegocio as e:
        return JsonResponse({"valida": False, "errores": [e.mensaje]})
    return JsonResponse(simulacion_a_json(sim))


@negocio_requerido
def compra(request, compra_id):
    obj = de_mi_tienda(request, Compra, compra_id)
    return render(request, "creditos/compra.html", {
        "compra": obj, "detalles": obj.detalles.order_by("linea"),
        "obligaciones": obj.obligaciones.order_by("numero"), "condicion": obj.condicion,
        "anulacion": obj.anulaciones.select_related("registrada_por").first(),
        "no_anulable": s.por_que_no_anular_compra(obj), "motivo_minimo": s.MOTIVO_MINIMO,
    })


@negocio_requerido
@require_POST
def anular_compra(request, compra_id):
    """Anula una venta registrada por error (sin borrarla): evento trazable con motivo."""
    try:
        s.anular_compra(request.user, request.tienda, compra_id, request.POST.get("motivo"), request)
        messages.success(request, "Venta anulada. Sus obligaciones ya no se cobran y el crédito del cliente se liberó.")
    except s.ErrorNegocio as e:
        messages.error(request, e.mensaje)
    return redirect("creditos:compra", compra_id=compra_id)


@negocio_requerido
@require_POST
def anular_pago(request, pago_id):
    """Anula el último pago de la cuenta: sus obligaciones vuelven a quedar pendientes."""
    try:
        s.anular_pago(request.user, request.tienda, pago_id, request.POST.get("motivo"), request)
        messages.success(request, "Pago anulado. Las obligaciones que cancelaba vuelven a estar pendientes.")
    except s.ErrorNegocio as e:
        messages.error(request, e.mensaje)
    return redirect("creditos:comprobante", pago_id=pago_id)


@negocio_requerido
def compras(request):
    qs = Compra.objects.filter(tienda=request.tienda).select_related("cuenta").order_by("-fecha_compra", "-numero")
    pagina = Paginator(qs, 50).get_page(request.GET.get("p"))
    return render(request, "creditos/compras.html", {"pagina": pagina})


# ---------------------------------------------------------------------------
# Estados de cuenta (requisito 6)
# ---------------------------------------------------------------------------

def _corte_desde_url(texto):
    try:
        return timezone.make_aware(datetime.strptime(texto, FORMATO_CORTE))
    except ValueError:
        raise Http404("Corte inválido.")


@negocio_requerido
def ciclo(request, cuenta_id, corte):
    cuenta = s.obtener_cuenta(request.tienda, cuenta_id, request.user, request)
    corte_dt = _corte_desde_url(corte)
    if request.method == "POST":
        try:
            s.generar_estado(cuenta, corte_dt, request.user, request)
            messages.success(request, "Estado de cuenta generado. Sus importes quedan congelados.")
        except s.ErrorNegocio as e:
            messages.error(request, e.mensaje)
        return redirect("creditos:ciclo", cuenta_id=cuenta.pk, corte=corte)
    al_dia = _fecha(request.GET.get("al")) or timezone.localdate()
    resumen = s.resumen_ciclo(cuenta, corte_dt, al_dia)
    if not resumen["lineas"]:
        raise Http404("No hay obligaciones en ese ciclo.")
    return render(request, "creditos/ciclo.html", {
        "cuenta": cuenta, "r": resumen, "corte_url": corte,
        "puede_generar": resumen["estado"] is None and corte_dt <= timezone.now(),
    })


@negocio_requerido
def estados(request):
    if request.method == "POST":
        generados = s.generar_estados_pendientes(tienda=request.tienda, usuario=request.user, request=request)
        messages.success(request, f"Estados generados: {len(generados)}.")
        return redirect("creditos:estados")
    qs = EstadoCuenta.objects.filter(tienda=request.tienda).select_related("cuenta").order_by("-corte", "cuenta__codigo")
    return render(request, "creditos/estados.html", {
        "pagina": Paginator(qs, 50).get_page(request.GET.get("p")),
        "pendientes": s.cortes_pendientes_de_estado(request.tienda),
    })


# ---------------------------------------------------------------------------
# Pagos (requisito 5 y Anexo A: prelación)
# ---------------------------------------------------------------------------

@negocio_requerido
def pago(request, cuenta_id):
    cuenta = s.obtener_cuenta(request.tienda, cuenta_id, request.user, request)
    pendientes = cuenta.obligaciones.filter(estado=Obligacion.Estado.PENDIENTE).select_related("compra").order_by("vencimiento", "compra__numero", "numero")
    seleccion = request.POST.getlist("obligacion")
    if request.method == "POST":
        try:
            clave = uuid.UUID(request.POST.get("clave", ""))
        except ValueError:
            clave = uuid.uuid4()
        try:
            p = s.registrar_pago(request.user, request.tienda, cuenta.pk, seleccion, _fecha(request.POST.get("fecha_efectiva")),
                                 request.POST.get("importe", ""), clave, request=request)
        except s.ErrorNegocio as e:
            messages.error(request, e.mensaje)
        else:
            messages.success(request, f"Pago registrado. Comprobante N° {p.numero:06d}.")
            return redirect("creditos:comprobante", pago_id=p.pk)
    return render(request, "creditos/pago.html", {
        "cuenta": cuenta, "pendientes": pendientes, "seleccion": seleccion,
        "fecha": request.POST.get("fecha_efectiva") or timezone.localdate().isoformat(),
        "importe": request.POST.get("importe", ""), "clave": request.POST.get("clave") or str(uuid.uuid4()),
        "hoy": timezone.localdate(),
    })


@negocio_requerido
@require_POST
def api_calcular_pago(request, cuenta_id):
    cuenta = s.obtener_cuenta(request.tienda, cuenta_id, request.user, request)
    try:
        d = json.loads(request.body or "{}")
        liq = s.calcular_pago(cuenta, d.get("obligaciones", []), _fecha(d.get("fecha")))
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Solicitud inválida."}, status=400)
    except s.ErrorNegocio as e:
        return JsonResponse({"ok": False, "error": e.mensaje})
    return JsonResponse({
        "ok": True, "simbolo": SIMBOLO_MONEDA.get(cuenta.moneda, cuenta.moneda),
        "items": [{"concepto": str(it.obligacion), "vencimiento": it.obligacion.vencimiento.strftime("%d/%m/%Y"),
                   "dias_mora": it.dias_mora, "mora": _t(it.mora), "interes": _t(it.interes), "capital": _t(it.capital),
                   "total": _t(it.total)} for it in liq.items],
        "mora": _t(liq.mora), "interes": _t(liq.interes), "capital": _t(liq.capital), "total": _t(liq.total),
    })


@negocio_requerido
def comprobante(request, pago_id):
    p = de_mi_tienda(request, Pago, pago_id)
    return render(request, "creditos/comprobante.html", {
        "pago": p, "aplicaciones": p.aplicaciones.select_related("obligacion__compra").order_by("obligacion__vencimiento"),
        "anulacion": p.anulaciones.select_related("registrada_por").first(),
        "no_anulable": s.por_que_no_anular_pago(p), "motivo_minimo": s.MOTIVO_MINIMO,
    })


@negocio_requerido
def pagos(request):
    qs = Pago.objects.filter(tienda=request.tienda).select_related("cuenta").order_by("-fecha_efectiva", "-numero")
    return render(request, "creditos/pagos.html", {"pagina": Paginator(qs, 50).get_page(request.GET.get("p"))})
