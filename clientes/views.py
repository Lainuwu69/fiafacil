"""Vistas de clientes del negocio (requisito 3): alta, baja, condiciones versionadas y acceso al portal."""

import json
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from clientes.forms import AccesoForm, CondicionForm, CuentaForm
from clientes.models import CuentaCliente
from clientes.servicios import abrir_cuenta, dar_acceso_cliente
from core.accesos import de_mi_tienda
from core.models import Auditoria
from creditos import finanzas as fin
from creditos import servicios as s
from creditos.models import Compra, Obligacion, Pago
from cuentas.permisos import negocio_requerido


@negocio_requerido
def lista(request):
    q = request.GET.get("q", "").strip()
    ver = request.GET.get("ver", "activos")
    cuentas = CuentaCliente.objects.filter(tienda=request.tienda).annotate(
        deuda=Sum("obligaciones__total", filter=Q(obligaciones__estado=Obligacion.Estado.PENDIENTE)),
    )
    if ver == "activos":
        cuentas = cuentas.filter(activo=True)
    elif ver == "baja":
        cuentas = cuentas.filter(activo=False)
    if q:
        cuentas = cuentas.filter(Q(nombre__icontains=q) | Q(documento__icontains=q) | Q(codigo__iexact=q))
    filas = [{"cuenta": c, "deuda": c.deuda or Decimal("0"), "disponible": s.disponible(c)} for c in cuentas.order_by("codigo")]
    return render(request, "clientes/lista.html", {"filas": filas, "q": q, "ver": ver})


@negocio_requerido
def nuevo(request):
    form = CuentaForm(request.POST or None, tienda=request.tienda, prefix="c")
    cond = CondicionForm(request.POST or None, prefix="k", initial={"tasa_periodo": 360, "mora_periodo": 360})
    if request.method == "POST" and form.is_valid() and cond.is_valid():
        try:
            cuenta = abrir_cuenta(request.tienda, request.user, form.cleaned_data, cond.a_datos(),
                                  vigente_desde=cond.cleaned_data.get("vigente_desde"), request=request)
        except s.ErrorNegocio as e:
            cond.add_error(None, e.mensaje)
        else:
            messages.success(request, f"Cliente {cuenta.codigo} {cuenta.nombre} registrado con sus condiciones (versión 1).")
            return redirect("clientes:detalle", cuenta_id=cuenta.pk)
    return render(request, "clientes/form.html", {"form": form, "cond": cond, "titulo": "Nuevo cliente"})


@negocio_requerido
def detalle(request, cuenta_id):
    cuenta = s.obtener_cuenta(request.tienda, cuenta_id, request.user, request)
    vigente = cuenta.condicion_vigente()
    pendientes = list(cuenta.obligaciones.filter(estado=Obligacion.Estado.PENDIENTE).select_related("compra").order_by("vencimiento", "numero"))
    cortes = [{"corte": c, "estado": cuenta.estados.filter(corte=c).first()} for c in s.cortes_de_cuenta(cuenta)]
    return render(request, "clientes/detalle.html", {
        "cuenta": cuenta, "vigente": vigente, "condiciones": cuenta.condiciones.order_by("-version"),
        "exposicion": s.exposicion(cuenta), "disponible": s.disponible(cuenta, vigente),
        "pendientes": pendientes, "deuda": sum((o.total for o in pendientes), Decimal("0")),
        "tem": s.tasa_compensatoria(vigente).tem() if vigente else None,
        "tea": s.tasa_compensatoria(vigente).tea() if vigente else None,
        "compras": Compra.objects.filter(cuenta=cuenta).order_by("-fecha_compra")[:10],
        "pagos": Pago.objects.filter(cuenta=cuenta).order_by("-fecha_efectiva", "-numero")[:10],
        "cortes": cortes,
        "hoy": timezone.localdate(),
    })


@negocio_requerido
def editar(request, cuenta_id):
    cuenta = s.obtener_cuenta(request.tienda, cuenta_id, request.user, request)
    form = CuentaForm(request.POST or None, instance=cuenta, tienda=request.tienda, prefix="c")
    if request.method == "POST" and form.is_valid():
        form.save()
        Auditoria.registrar(Auditoria.Evento.MODIFICACION, f"Datos generales del cliente {cuenta.codigo} actualizados.",
                            usuario=request.user, tienda=request.tienda, objeto=cuenta, request=request)
        messages.success(request, "Datos del cliente actualizados.")
        return redirect("clientes:detalle", cuenta_id=cuenta.pk)
    return render(request, "clientes/form.html", {"form": form, "cuenta": cuenta, "titulo": f"Editar {cuenta.codigo}"})


@negocio_requerido
def condicion(request, cuenta_id):
    """Nueva versión de condiciones (RN10). Las compras anteriores conservan su versión."""
    cuenta = s.obtener_cuenta(request.tienda, cuenta_id, request.user, request)
    vigente = cuenta.condicion_vigente()
    inicial = CondicionForm.desde_condicion(vigente) if vigente else {}
    cond = CondicionForm(request.POST or None, prefix="k", initial=inicial)
    if request.method == "POST" and cond.is_valid():
        try:
            nueva = s.guardar_condicion(cuenta, request.user, cond.a_datos(), vigente_desde=cond.cleaned_data.get("vigente_desde"),
                                        request=request)
        except s.ErrorNegocio as e:
            cond.add_error(None, e.mensaje)
        else:
            messages.success(request, f"Condiciones actualizadas (versión {nueva.version}). Las compras anteriores conservan sus condiciones.")
            return redirect("clientes:detalle", cuenta_id=cuenta.pk)
    return render(request, "clientes/condicion.html", {"cuenta": cuenta, "cond": cond, "vigente": vigente})


@negocio_requerido
@require_POST
def cambiar_estado(request, cuenta_id):
    cuenta = s.obtener_cuenta(request.tienda, cuenta_id, request.user, request)
    cuenta.activo = not cuenta.activo
    cuenta.save(update_fields=["activo"])
    texto = "reactivada" if cuenta.activo else "dada de baja (conserva su historial y su deuda)"
    Auditoria.registrar(Auditoria.Evento.ALTA if cuenta.activo else Auditoria.Evento.BAJA, f"Cuenta {cuenta.codigo} {texto}.",
                        usuario=request.user, tienda=request.tienda, objeto=cuenta, request=request)
    messages.success(request, f"Cuenta {cuenta.codigo} {texto}.")
    return redirect("clientes:detalle", cuenta_id=cuenta.pk)


@negocio_requerido
def acceso(request, cuenta_id):
    cuenta = s.obtener_cuenta(request.tienda, cuenta_id, request.user, request)
    form = AccesoForm(request.POST or None, initial={"email": cuenta.usuario.email if cuenta.usuario else cuenta.correo})
    if request.method == "POST" and form.is_valid():
        try:
            cliente, creado = dar_acceso_cliente(cuenta, form.cleaned_data["email"], form.cleaned_data.get("password"),
                                                 request.user, request)
        except s.ErrorNegocio as e:
            form.add_error(None, e.mensaje)
        else:
            messages.success(request, f"El cliente ya puede entrar al portal con {cliente.email}"
                                      f"{' y la contraseña inicial que le asignaste' if creado else ' (usa su contraseña actual)'}.")
            return redirect("clientes:detalle", cuenta_id=cuenta.pk)
    return render(request, "clientes/acceso.html", {"cuenta": cuenta, "form": form})


@negocio_requerido
@require_POST
def api_tasa_equivalente(request):
    """Convierte una tasa escrita en el formulario a TEM y TEA (cálculo en el servidor)."""
    try:
        d = json.loads(request.body or "{}")
        porcentaje = Decimal(str(d.get("porcentaje", "")).strip())
        tasa = fin.Tasa(d.get("tipo", ""), porcentaje / 100, int(d.get("periodo") or 360),
                        int(d["capitalizacion"]) if d.get("capitalizacion") else None)
    except (ValueError, InvalidOperation, json.JSONDecodeError, fin.ErrorFinanciero) as e:
        mensaje = str(e) if isinstance(e, fin.ErrorFinanciero) else "Escribe una tasa válida (por ejemplo 24)."
        return JsonResponse({"ok": False, "error": mensaje})
    supuestos = []
    if tasa.tipo == "NOMINAL" and not d.get("capitalizacion"):
        supuestos.append("Sin capitalización indicada: se asume diaria (convención del curso).")
    return JsonResponse({
        "ok": True,
        "tem": str(tasa.tem()), "tea": str(tasa.tea()),
        "tem_texto": fin.formato_tasa(tasa.tem()), "tea_texto": fin.formato_tasa(tasa.tea()),
        "supuestos": supuestos,
    })
