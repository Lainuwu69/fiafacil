"""
ALGORITMO DE FÍAFÁCIL (capítulo 4 del informe): operaciones que leen y escriben datos.

Este módulo une el modelo matemático (finanzas.py) con la base de datos. Cada
operación que escribe datos financieros:

1. Verifica que la cuenta pertenezca a la tienda del usuario (RN01). Si no, se
   audita el intento y se responde "no encontrado" (404).
2. Revisa la clave de idempotencia: si la misma solicitud llega dos veces,
   devuelve el registro existente en lugar de duplicarlo.
3. Abre una transacción (transaction.atomic) y bloquea la tienda y la cuenta
   (select_for_update) para que dos operaciones simultáneas no superen el
   límite ni cobren dos veces.
4. Recalcula todo en el servidor; nunca confía en un total enviado por el navegador.
5. Registra el evento en la auditoría.

Funciones principales (pseudocódigo del capítulo 4):
    exposicion, disponible                RN06
    guardar_condicion                     RN10 + tope BCRP
    calcular_compra / registrar_compra    4.1 RegistrarCompra
    resumen_ciclo / generar_estado        4.3 GenerarEstado
    calcular_pago / registrar_pago        4.3 RegistrarPago (mora → interés → capital)
    flujo_cobranzas                       flujo de caja proyectado
"""

from collections import OrderedDict, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q, Sum
from django.http import Http404
from django.utils import timezone

from clientes.models import CondicionCredito, CuentaCliente
from core.constantes import SIMBOLO_MONEDA, Modalidad
from core.modelos_base import siguiente_numero
from core.models import Auditoria, TopeTasa
from creditos import finanzas as fin
from creditos.finanzas import CERO, ErrorFinanciero, r2
from creditos.models import Anulacion, Compra, DetalleCompra, EstadoCuenta, EstadoDetalle, Obligacion, Pago, PagoAplicacion
from tiendas.models import Articulo, Tienda

Q15 = Decimal("1E-15")


class ErrorNegocio(Exception):
    """Regla de negocio incumplida. El mensaje se muestra tal cual al usuario."""

    def __init__(self, mensaje, datos=None):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.datos = datos or {}


def _ahora(ahora=None):
    return ahora or timezone.now()


def _soles(cuenta, monto):
    """Formatea un importe con el símbolo de la moneda de la cuenta: S/ 1,250.50."""
    return f"{SIMBOLO_MONEDA.get(cuenta.moneda, cuenta.moneda)} {r2(monto):,.2f}"


def _q15(valor):
    return None if valor is None else valor.quantize(Q15)


# ---------------------------------------------------------------------------
# Acceso por tienda (RN01)
# ---------------------------------------------------------------------------

def obtener_cuenta(tienda, cuenta_id, usuario=None, request=None):
    """Devuelve la cuenta solo si pertenece a la tienda. Si no, audita y lanza 404."""
    try:
        return CuentaCliente.objects.select_related("tienda").get(pk=cuenta_id, tienda=tienda)
    except (CuentaCliente.DoesNotExist, ValidationError, ValueError):
        Auditoria.registrar(
            Auditoria.Evento.ACCESO_DENEGADO,
            f"Intento de acceder a una cuenta que no pertenece a la tienda {tienda.codigo}.",
            usuario=usuario,
            tienda=tienda,
            datos={"cuenta_id": str(cuenta_id)},
            request=request,
        )
        raise Http404("La cuenta no existe en esta tienda.")


# ---------------------------------------------------------------------------
# Tasas de una condición
# ---------------------------------------------------------------------------

def tasa_compensatoria(condicion):
    return fin.Tasa(condicion.tasa_tipo, condicion.tasa_valor, condicion.tasa_periodo, condicion.tasa_capitalizacion)


def tasa_moratoria(condicion):
    return fin.Tasa(condicion.mora_tipo, condicion.mora_valor, condicion.mora_periodo, condicion.mora_capitalizacion)


def condicion_en(cuenta, momento):
    """Versión de condiciones vigente en un momento dado (RN10)."""
    return (
        cuenta.condiciones.filter(vigente_desde__lte=momento)
        .filter(Q(vigente_hasta__isnull=True) | Q(vigente_hasta__gt=momento))
        .order_by("-version")
        .first()
    )


# ---------------------------------------------------------------------------
# Exposición y crédito disponible (RN06)
# ---------------------------------------------------------------------------

def exposicion(cuenta):
    """Capital comprometido: capital de las compras mensuales pendientes + saldo de las cuotas.

    El saldo de un plan en cuotas es la suma de las amortizaciones de sus cuotas pendientes
    (incluye la gracia capitalizada, porque las cuotas amortizan Pg). No incluye intereses futuros.
    """
    total = cuenta.obligaciones.filter(estado=Obligacion.Estado.PENDIENTE).aggregate(s=Sum("capital"))["s"]
    return r2(total or CERO)


def disponible(cuenta, condicion=None):
    condicion = condicion or cuenta.condicion_vigente()
    if condicion is None:
        return r2(CERO)
    return fin.disponible(condicion.limite, exposicion(cuenta))


# ---------------------------------------------------------------------------
# Condiciones de crédito (RN10 + topes del BCRP)
# ---------------------------------------------------------------------------

CAMPOS_CONDICION = (
    "tasa_tipo", "tasa_valor", "tasa_periodo", "tasa_capitalizacion",
    "mora_tipo", "mora_valor", "mora_periodo", "mora_capitalizacion",
    "limite", "plazo_max", "dia_corte", "hora_corte", "dia_pago",
)


def verificar_topes(moneda, tasa_comp, tasa_mora, fecha):
    """Compara las TEA pactadas con los topes del BCRP vigentes. Devuelve la lista de excesos."""
    excesos = []
    for tipo, tasa, nombre in (
        (TopeTasa.Tipo.COMPENSATORIA, tasa_comp, "compensatoria"),
        (TopeTasa.Tipo.MORATORIA, tasa_mora, "moratoria"),
    ):
        tope = (
            TopeTasa.objects.filter(moneda=moneda, tipo=tipo, vigente_desde__lte=fecha)
            .filter(Q(vigente_hasta__isnull=True) | Q(vigente_hasta__gte=fecha))
            .order_by("-vigente_desde")
            .first()
        )
        if tope and tasa.tea() > tope.tasa_efectiva_anual:
            excesos.append(
                f"La TEA {nombre} equivalente ({fin.formato_tasa(tasa.tea())}) supera el tope del BCRP "
                f"vigente ({fin.formato_tasa(tope.tasa_efectiva_anual)}). Fuente: {tope.fuente_url}"
            )
    return excesos


def guardar_condicion(cuenta, usuario, datos, *, vigente_desde=None, request=None, ahora=None):
    """Crea una versión nueva de condiciones y cierra la anterior (RN10).

    Las compras ya registradas conservan la versión con la que se hicieron.
    `datos` trae los campos de CAMPOS_CONDICION con las tasas en decimal (0.24).
    """
    ahora = _ahora(ahora)
    vigente_desde = vigente_desde or ahora
    if vigente_desde > ahora:
        raise ErrorNegocio("Las condiciones no pueden empezar a regir en el futuro.")
    with transaction.atomic():
        cuenta = CuentaCliente.objects.select_for_update().get(pk=cuenta.pk)
        actual = cuenta.condicion_vigente()
        if actual is not None:
            if vigente_desde <= actual.vigente_desde:
                raise ErrorNegocio(
                    f"La nueva versión debe regir después de la actual (vigente desde {timezone.localtime(actual.vigente_desde):%d/%m/%Y %H:%M})."
                )
            ultima = cuenta.compras.order_by("-fecha_compra").values_list("fecha_compra", flat=True).first()
            if ultima and vigente_desde <= ultima:
                raise ErrorNegocio(
                    "La nueva versión no puede regir antes de la última compra registrada "
                    f"({timezone.localtime(ultima):%d/%m/%Y %H:%M}); las compras conservan sus condiciones (RN10)."
                )
        nueva = CondicionCredito(
            cuenta=cuenta,
            version=(actual.version + 1) if actual else 1,
            vigente_desde=vigente_desde,
            creado_por=usuario,
            **{k: datos.get(k) for k in CAMPOS_CONDICION},
        )
        try:
            # Las restricciones UNIQUE (una sola versión vigente) las verifica PostgreSQL al guardar,
            # después de cerrar la versión anterior; aquí se validan campos y reglas del modelo.
            nueva.full_clean(exclude=["creado_por"], validate_constraints=False)
        except ValidationError as e:
            raise ErrorNegocio(" ".join(m for msgs in e.message_dict.values() for m in msgs), {"campos": e.message_dict})
        try:
            excesos = verificar_topes(cuenta.moneda, tasa_compensatoria(nueva), tasa_moratoria(nueva), vigente_desde.date())
        except ErrorFinanciero as e:
            raise ErrorNegocio(str(e))
        if excesos:
            raise ErrorNegocio(" ".join(excesos))
        if actual is not None:
            actual.vigente_hasta = vigente_desde
            actual.save(update_fields=["vigente_hasta"])
        nueva.save()
        Auditoria.registrar(
            Auditoria.Evento.CONDICION,
            f"Condiciones v{nueva.version} de la cuenta {cuenta.codigo}: tasa {fin.formato_tasa(nueva.tasa_valor)} "
            f"{nueva.get_tasa_tipo_display().lower()}, límite {_soles(cuenta, nueva.limite)}.",
            usuario=usuario,
            tienda=cuenta.tienda,
            objeto=nueva,
            request=request,
        )
        return nueva


# ---------------------------------------------------------------------------
# Compras (4.1 RegistrarCompra)
# ---------------------------------------------------------------------------

@dataclass
class LineaCalculada:
    articulo: Articulo
    cantidad: Decimal
    precio_unitario: Decimal
    precio_contado: Decimal
    importe: Decimal
    importe_contado: Decimal


@dataclass
class Simulacion:
    """Resultado de calcular una compra sin grabarla (lo que muestra la pantalla en vivo)."""

    cuenta: CuentaCliente
    fecha_compra: datetime
    modalidad: str
    n_cuotas: int | None
    condicion: CondicionCredito | None = None
    lineas: list = field(default_factory=list)
    capital: Decimal = CERO
    capital_contado: Decimal = CERO
    ciclo: fin.Ciclo | None = None
    mensual: fin.ResultadoMensual | None = None
    cuotas: fin.ResultadoCuotas | None = None
    exposicion_actual: Decimal = CERO
    nueva_exposicion: Decimal = CERO
    limite: Decimal = CERO
    tcea: Decimal | None = None
    tcea_contado: Decimal | None = None
    alternativas: list = field(default_factory=list)
    errores: list = field(default_factory=list)

    @property
    def valida(self):
        return not self.errores

    @property
    def interes(self):
        if self.mensual:
            return self.mensual.interes
        if self.cuotas:
            return self.cuotas.interes_total
        return CERO

    @property
    def total(self):
        return self.capital + self.interes

    @property
    def disponible_antes(self):
        return fin.disponible(self.limite, self.exposicion_actual)

    @property
    def disponible_despues(self):
        return fin.disponible(self.limite, self.exposicion_actual + self.nueva_exposicion)

    def cortes_afectados(self):
        """Cortes de los ciclos en los que caerán las obligaciones de la compra."""
        if not self.ciclo:
            return []
        if self.modalidad == Modalidad.MENSUAL:
            return [self.ciclo.corte]
        hora = timezone.localtime(self.ciclo.corte).timetz()
        n = self.n_cuotas or 0
        return [datetime.combine(fin.sumar_meses(self.ciclo.corte.date(), k), hora) for k in range(1, n + 1)]


def _normalizar_lineas(lineas):
    """Acepta [{'articulo_id': ..., 'cantidad': ...}] y devuelve [(id, Decimal)]."""
    salida = []
    for linea in lineas or []:
        try:
            cantidad = fin.D(str(linea.get("cantidad", "")).strip())
        except Exception:
            raise ErrorNegocio("Cantidad inválida: escribe un número con punto decimal, por ejemplo 1.5.")
        salida.append((linea.get("articulo_id"), cantidad))
    return salida


def calcular_compra(cuenta, lineas, modalidad, n_cuotas, fecha_compra, ahora=None):
    """Calcula una compra completa sin grabarla. Acumula los errores en lugar de detenerse."""
    ahora = _ahora(ahora)
    sim = Simulacion(cuenta=cuenta, fecha_compra=fecha_compra, modalidad=modalidad, n_cuotas=None)
    err = sim.errores

    if cuenta.tienda.estado != Tienda.Estado.ACTIVA:
        err.append("La tienda no está activa; no puede registrar ventas hasta que la plataforma la active.")
    if not cuenta.activo:
        err.append(f"La cuenta {cuenta.codigo} está dada de baja; no admite compras nuevas (RN09).")
    if modalidad not in Modalidad.values:
        err.append("Elige la modalidad: pago a fin de mes o en cuotas.")
        return sim
    if fecha_compra is None or fecha_compra.tzinfo is None:
        err.append("Indica la fecha y hora de la compra.")
        return sim
    if fecha_compra > ahora:
        err.append(
            f"La fecha de la compra ({timezone.localtime(fecha_compra):%d/%m/%Y %H:%M}) no puede ser futura."
        )

    condicion = condicion_en(cuenta, fecha_compra)
    sim.condicion = condicion
    if condicion is None:
        err.append("La cuenta no tenía condiciones de crédito vigentes en la fecha de la compra.")
        return sim
    sim.limite = condicion.limite

    try:
        pares = _normalizar_lineas(lineas)
    except ErrorNegocio as e:
        err.append(e.mensaje)
        return sim
    if not pares:
        err.append("Agrega al menos un artículo a la venta.")
        return sim
    articulos = {str(a.pk): a for a in Articulo.objects.filter(tienda=cuenta.tienda, pk__in=[p[0] for p in pares if p[0]])}
    for articulo_id, cantidad in pares:
        articulo = articulos.get(str(articulo_id))
        if articulo is None:
            err.append("Uno de los artículos no existe en el catálogo de esta tienda.")
            continue
        if not articulo.activo:
            err.append(f"El artículo «{articulo}» está dado de baja.")
        if cantidad <= 0 or cantidad.as_tuple().exponent < -3:
            err.append(f"Cantidad de «{articulo}»: debe ser mayor que cero y tener como máximo 3 decimales.")
            continue
        if modalidad == Modalidad.MENSUAL and not articulo.permite_mensual:
            err.append(f"«{articulo}» no se vende a fin de mes, solo en cuotas.")
        if modalidad == Modalidad.CUOTAS and not articulo.permite_cuotas:
            err.append(f"«{articulo}» no se vende en cuotas, solo a fin de mes.")
        sim.lineas.append(LineaCalculada(
            articulo, cantidad, articulo.precio_credito, articulo.precio_contado,
            r2(cantidad * articulo.precio_credito), r2(cantidad * articulo.precio_contado),
        ))
    if not sim.lineas:
        return sim
    sim.capital = sum((ln.importe for ln in sim.lineas), CERO)
    sim.capital_contado = sum((ln.importe_contado for ln in sim.lineas), CERO)

    if modalidad == Modalidad.CUOTAS:
        try:
            sim.n_cuotas = int(n_cuotas)
        except (TypeError, ValueError):
            err.append("Indica el número de cuotas.")
            return sim
        if not 1 <= sim.n_cuotas <= condicion.plazo_max:
            err.append(f"El número de cuotas ({sim.n_cuotas}) debe estar entre 1 y el máximo pactado ({condicion.plazo_max}).")
            return sim

    try:
        tasa = tasa_compensatoria(condicion)
        sim.ciclo = fin.ciclo_de_compra(fecha_compra, condicion.dia_corte, condicion.hora_corte, condicion.dia_pago)
        if modalidad == Modalidad.MENSUAL:
            sim.mensual = fin.compra_mensual(sim.capital, tasa, fecha_compra, sim.ciclo.fecha_pago)
            sim.nueva_exposicion = sim.capital
            sim.tcea = fin.tcea(sim.capital, fin.flujos_de_mensual(sim.mensual))
            sim.tcea_contado = fin.tcea(sim.capital_contado, fin.flujos_de_mensual(sim.mensual))
        else:
            sim.cuotas = fin.compra_en_cuotas(sim.capital, tasa, fecha_compra, sim.ciclo.fecha_pago, sim.n_cuotas)
            sim.nueva_exposicion = sim.cuotas.capital_con_gracia  # RN06: con la gracia capitalizada
            sim.tcea = fin.tcea(sim.capital, fin.flujos_de_cuotas(sim.cuotas))
            sim.tcea_contado = fin.tcea(sim.capital_contado, fin.flujos_de_cuotas(sim.cuotas))
        sim.alternativas = fin.comparar_alternativas(
            sim.capital, sim.capital_contado, tasa, fecha_compra, sim.ciclo, condicion.plazo_max,
            permite_mensual=all(ln.articulo.permite_mensual for ln in sim.lineas),
            permite_cuotas=all(ln.articulo.permite_cuotas for ln in sim.lineas),
        )
    except ErrorFinanciero as e:
        err.append(str(e))
        return sim

    # RN06: E + nuevo capital ≤ L
    sim.exposicion_actual = exposicion(cuenta)
    if not fin.cabe_en_limite(condicion.limite, sim.exposicion_actual, sim.nueva_exposicion):
        err.append(
            f"La compra excede el límite de crédito. Disponible: {_soles(cuenta, sim.disponible_antes)}; "
            f"se necesita: {_soles(cuenta, sim.nueva_exposicion)}."
        )

    # Una compra no puede entrar a un ciclo cuyo estado de cuenta ya se generó.
    cerrados = set(EstadoCuenta.objects.filter(cuenta=cuenta, corte__in=sim.cortes_afectados()).values_list("corte", flat=True))
    if cerrados:
        primero = timezone.localtime(min(cerrados))
        err.append(f"El estado de cuenta del corte {primero:%d/%m/%Y} ya fue generado; no se pueden agregar compras a ese ciclo.")
    return sim


def _texto_errores(sim):
    return " ".join(sim.errores)


def registrar_compra(usuario, tienda, cuenta_id, lineas, modalidad, n_cuotas, fecha_compra, clave,
                     request=None, ahora=None):
    """Graba la compra, sus líneas y sus obligaciones en una sola transacción (4.1)."""
    cuenta = obtener_cuenta(tienda, cuenta_id, usuario, request)
    previa = Compra.objects.filter(tienda=tienda, clave_idempotencia=clave).first()
    if previa:
        return previa
    try:
        with transaction.atomic():
            Tienda.objects.select_for_update().get(pk=tienda.pk)  # serializa la numeración
            cuenta = CuentaCliente.objects.select_for_update().select_related("tienda").get(pk=cuenta.pk)
            sim = calcular_compra(cuenta, lineas, modalidad, n_cuotas, fecha_compra, ahora)
            if not sim.valida:
                raise ErrorNegocio(_texto_errores(sim), {"errores": sim.errores})
            compra = Compra.objects.create(
                tienda=tienda,
                numero=siguiente_numero(Compra.objects.filter(tienda=tienda)),
                cuenta=cuenta,
                condicion=sim.condicion,
                moneda=cuenta.moneda,
                fecha_compra=fecha_compra,
                modalidad=modalidad,
                n_cuotas=sim.n_cuotas,
                capital=sim.capital,
                corte=sim.ciclo.corte,
                fecha_pago=sim.ciclo.fecha_pago,
                dias=sim.mensual.dias if sim.mensual else sim.cuotas.dias_gracia,
                tasa_periodo=_q15(sim.mensual.tasa_periodo if sim.mensual else sim.cuotas.tem),
                interes=sim.interes,
                capital_con_gracia=sim.cuotas.capital_con_gracia if sim.cuotas else None,
                cuota=sim.cuotas.cuota if sim.cuotas else None,
                total=sim.total,
                tcea=_q15(sim.tcea),
                tcea_contado=_q15(sim.tcea_contado),
                clave_idempotencia=clave,
                registrada_por=usuario,
            )
            DetalleCompra.objects.bulk_create([
                DetalleCompra(
                    compra=compra, linea=i, articulo=ln.articulo, descripcion=ln.articulo.descripcion,
                    unidad=ln.articulo.get_unidad_display(), cantidad=ln.cantidad, precio_unitario=ln.precio_unitario,
                    precio_contado=ln.precio_contado, importe=ln.importe,
                )
                for i, ln in enumerate(sim.lineas, start=1)
            ])
            if sim.mensual:
                obligaciones = [Obligacion(
                    tienda=tienda, cuenta=cuenta, compra=compra, numero=1, tipo=Obligacion.Tipo.MENSUAL,
                    corte=sim.ciclo.corte, vencimiento=sim.ciclo.fecha_pago,
                    capital=sim.mensual.capital, interes=sim.mensual.interes, total=sim.mensual.total,
                )]
            else:
                obligaciones = [
                    Obligacion(
                        tienda=tienda, cuenta=cuenta, compra=compra, numero=f.numero, tipo=Obligacion.Tipo.CUOTA,
                        corte=corte, vencimiento=f.vencimiento, saldo_inicial=f.saldo_inicial,
                        capital=f.amortizacion, interes=f.interes, total=f.cuota, saldo_final=f.saldo_final,
                    )
                    for f, corte in zip(sim.cuotas.filas, sim.cortes_afectados())
                ]
            Obligacion.objects.bulk_create(obligaciones)
            Auditoria.registrar(
                Auditoria.Evento.COMPRA,
                f"Compra N° {compra.numero} de {cuenta.codigo}: {_soles(cuenta, compra.capital)} "
                f"({'fin de mes' if compra.modalidad == Modalidad.MENSUAL else f'{compra.n_cuotas} cuotas'}).",
                usuario=usuario, tienda=tienda, objeto=compra,
                datos={"capital": str(compra.capital), "total": str(compra.total), "modalidad": modalidad,
                       "n_cuotas": sim.n_cuotas, "fecha_compra": fecha_compra.isoformat()},
                request=request,
            )
            return compra
    except ErrorNegocio as e:
        Auditoria.registrar(
            Auditoria.Evento.COMPRA_RECHAZADA, f"Compra rechazada en {cuenta.codigo}: {e.mensaje}"[:300],
            usuario=usuario, tienda=tienda, objeto=cuenta, datos={"motivo": e.mensaje}, request=request,
        )
        raise
    except IntegrityError:
        # Dos solicitudes con la misma clave al mismo tiempo: la segunda devuelve la primera.
        previa = Compra.objects.filter(tienda=tienda, clave_idempotencia=clave).first()
        if previa:
            return previa
        raise


# ---------------------------------------------------------------------------
# Estados de cuenta (4.3 GenerarEstado)
# ---------------------------------------------------------------------------

def _descripcion(obligacion):
    compra = obligacion.compra
    if obligacion.tipo == Obligacion.Tipo.CUOTA:
        return f"Cuota {obligacion.numero}/{compra.n_cuotas} de la compra N° {compra.numero}"
    detalles = list(compra.detalles.all()[:2])
    texto = detalles[0].descripcion if detalles else "Compra"
    if compra.detalles.count() > 1:
        texto += " y otros"
    return f"Compra N° {compra.numero}: {texto}"[:200]


def obligaciones_del_ciclo(cuenta, corte):
    """Obligaciones vigentes del ciclo (las de ventas anuladas no se cobran)."""
    return (
        Obligacion.objects.filter(cuenta=cuenta, corte=corte)
        .exclude(estado=Obligacion.Estado.ANULADA)
        .select_related("compra", "compra__condicion")
        .order_by("compra__fecha_compra", "compra__numero", "numero")
    )


def cortes_de_cuenta(cuenta):
    """Cortes con obligaciones vigentes o con estado ya generado, del más reciente al más antiguo."""
    vigentes = set(cuenta.obligaciones.exclude(estado=Obligacion.Estado.ANULADA).values_list("corte", flat=True))
    generados = set(cuenta.estados.values_list("corte", flat=True))
    return sorted(vigentes | generados, reverse=True)


def generar_estado(cuenta, corte, usuario=None, request=None, ahora=None):
    """Genera (una sola vez) el listado de pago del ciclo, cuando el corte ya se cumplió."""
    ahora = _ahora(ahora)
    if corte > ahora:
        raise ErrorNegocio(
            f"El corte del {timezone.localtime(corte):%d/%m/%Y %H:%M} aún no se cumple; solo se puede ver la vista previa."
        )
    previo = EstadoCuenta.objects.filter(cuenta=cuenta, corte=corte).first()
    if previo:
        return previo
    try:
        with transaction.atomic():
            cuenta = CuentaCliente.objects.select_for_update().get(pk=cuenta.pk)
            lineas = list(obligaciones_del_ciclo(cuenta, corte))
            if not lineas:
                raise ErrorNegocio("No hay compras ni cuotas en ese ciclo.")
            capital = sum((o.capital for o in lineas), CERO)
            interes = sum((o.interes for o in lineas), CERO)
            estado = EstadoCuenta.objects.create(
                tienda=cuenta.tienda, cuenta=cuenta, corte=corte, fecha_pago=lineas[0].vencimiento,
                capital=capital, interes=interes, total=capital + interes, generado_por=usuario,
            )
            EstadoDetalle.objects.bulk_create([
                EstadoDetalle(
                    estado=estado, obligacion=o, orden=i, fecha_compra=o.compra.fecha_compra,
                    descripcion=_descripcion(o), dias=o.compra.dias if o.tipo == Obligacion.Tipo.MENSUAL else None,
                    capital=o.capital, interes=o.interes, total=o.total,
                )
                for i, o in enumerate(lineas, start=1)
            ])
            Auditoria.registrar(
                Auditoria.Evento.ESTADO,
                f"Estado de {cuenta.codigo} al corte {timezone.localtime(corte):%d/%m/%Y}: {_soles(cuenta, estado.total)}.",
                usuario=usuario, tienda=cuenta.tienda, objeto=estado, request=request,
            )
            return estado
    except IntegrityError:
        return EstadoCuenta.objects.get(cuenta=cuenta, corte=corte)


def generar_estados_pendientes(ahora=None, tienda=None, usuario=None, request=None):
    """Genera los estados de todos los cortes ya cumplidos que aún no tienen estado (comando diario).

    Con `tienda`, solo los de esa tienda (botón "Generar estados" del negocio).
    """
    ahora = _ahora(ahora)
    generados = []
    ciclos = Obligacion.objects.filter(corte__lte=ahora).exclude(estado=Obligacion.Estado.ANULADA)
    if tienda is not None:
        ciclos = ciclos.filter(tienda=tienda)
    ciclos = ciclos.values_list("cuenta_id", "corte").distinct()
    for cuenta_id, corte in ciclos:
        if EstadoCuenta.objects.filter(cuenta_id=cuenta_id, corte=corte).exists():
            continue
        cuenta = CuentaCliente.objects.select_related("tienda").get(pk=cuenta_id)
        generados.append(generar_estado(cuenta, corte, usuario=usuario, request=request, ahora=ahora))
    return generados


def cortes_pendientes_de_estado(tienda, ahora=None):
    """Cantidad de ciclos con corte cumplido y sin estado generado (aviso en pantalla)."""
    ahora = _ahora(ahora)
    ciclos = set(Obligacion.objects.filter(tienda=tienda, corte__lte=ahora).exclude(estado=Obligacion.Estado.ANULADA)
                 .values_list("cuenta_id", "corte").distinct())
    hechos = set(EstadoCuenta.objects.filter(tienda=tienda).values_list("cuenta_id", "corte"))
    return len(ciclos - hechos)


def resumen_ciclo(cuenta, corte, al_dia=None):
    """Datos para mostrar un ciclo: líneas (congeladas si ya hay estado), totales y mora como ítem aparte.

    La mora aparece separada: la ya cobrada (de los pagos) y la proyectada a la fecha `al_dia`
    para lo que sigue pendiente después del vencimiento.
    """
    al_dia = al_dia or timezone.localdate()
    estado = EstadoCuenta.objects.filter(cuenta=cuenta, corte=corte).first()
    obligaciones = list(obligaciones_del_ciclo(cuenta, corte))
    if estado:
        # El estado generado queda congelado: si luego se anuló una venta, la línea se muestra
        # marcada como anulada (ya no se cobra), pero el documento original no se altera.
        lineas = [
            {"orden": d.orden, "fecha_compra": d.fecha_compra, "descripcion": d.descripcion, "dias": d.dias,
             "capital": d.capital, "interes": d.interes, "total": d.total, "obligacion": d.obligacion,
             "anulada": d.obligacion.estado == Obligacion.Estado.ANULADA}
            for d in estado.detalles.select_related("obligacion").order_by("orden")
        ]
    else:
        lineas = [
            {"orden": i, "fecha_compra": o.compra.fecha_compra, "descripcion": _descripcion(o),
             "dias": o.compra.dias if o.tipo == Obligacion.Tipo.MENSUAL else None,
             "capital": o.capital, "interes": o.interes, "total": o.total, "obligacion": o}
            for i, o in enumerate(obligaciones, start=1)
        ]
    capital = sum((ln["capital"] for ln in lineas), CERO)
    interes = sum((ln["interes"] for ln in lineas), CERO)
    mora_pagada = (PagoAplicacion.objects.filter(obligacion__in=obligaciones, anulada=False)
                   .aggregate(s=Sum("mora"))["s"] or CERO)
    pendientes = [o for o in obligaciones if o.estado == Obligacion.Estado.PENDIENTE]
    mora_proyectada, dias_atraso = CERO, 0
    if pendientes and obligaciones and al_dia > obligaciones[0].vencimiento:
        liq = _liquidar(cuenta, pendientes, al_dia)
        mora_proyectada = sum((it.mora for it in liq), CERO)
        dias_atraso = max(it.dias_mora for it in liq)
    return {
        "corte": corte,
        "fecha_pago": obligaciones[0].vencimiento if obligaciones else (estado.fecha_pago if estado else None),
        "estado": estado,
        "lineas": lineas,
        "capital": capital,
        "interes": interes,
        "total": capital + interes,
        "mora_pagada": r2(mora_pagada),
        "mora_proyectada": r2(mora_proyectada),
        "dias_atraso": dias_atraso,
        "pendiente": sum((o.total for o in pendientes), CERO),
        "hay_anuladas": any(ln.get("anulada") for ln in lineas),
        "al_dia": al_dia,
    }


# ---------------------------------------------------------------------------
# Pagos (4.3 RegistrarPago)
# ---------------------------------------------------------------------------

@dataclass
class ItemLiquidacion:
    obligacion: Obligacion
    dias_mora: int
    mora: Decimal
    interes: Decimal
    capital: Decimal

    @property
    def total(self):
        return self.mora + self.interes + self.capital


@dataclass
class Liquidacion:
    cuenta: CuentaCliente
    fecha_efectiva: date
    items: list

    @property
    def mora(self):
        return sum((i.mora for i in self.items), CERO)

    @property
    def interes(self):
        return sum((i.interes for i in self.items), CERO)

    @property
    def capital(self):
        return sum((i.capital for i in self.items), CERO)

    @property
    def total(self):
        return self.mora + self.interes + self.capital


def _liquidar(cuenta, obligaciones, fecha):
    """Calcula la mora de cada obligación a una fecha (RN08).

    La mora se calcula sobre el TOTAL que debió pagarse en cada vencimiento (requisito 6:
    "el pago total que debería haber sido"): se agrupan las obligaciones de la cuenta con el
    mismo vencimiento y la misma tasa moratoria, M = R2(V_grupo × iₘ(días)), y M se reparte
    proporcionalmente entre ellas (la última absorbe los centavos del redondeo). Así la mora
    de una obligación no depende de cuáles se paguen juntas.
    """
    cache = {}
    items = []
    for o in obligaciones:
        cond = o.compra.condicion
        clave = (o.vencimiento, cond.mora_tipo, cond.mora_valor, cond.mora_periodo, cond.mora_capitalizacion)
        if clave not in cache:
            grupo = [
                g for g in Obligacion.objects.filter(cuenta=cuenta, vencimiento=o.vencimiento)
                .exclude(estado=Obligacion.Estado.ANULADA)
                .select_related("compra__condicion").order_by("compra__numero", "numero")
                if (g.compra.condicion.mora_tipo, g.compra.condicion.mora_valor, g.compra.condicion.mora_periodo,
                    g.compra.condicion.mora_capitalizacion) == clave[1:]
            ]
            base = sum((g.total for g in grupo), CERO)
            m = fin.calcular_mora(base, tasa_moratoria(cond), o.vencimiento, fecha)
            reparto, acumulado = {}, CERO
            for idx, g in enumerate(grupo):
                if idx == len(grupo) - 1:
                    parte = m.mora - acumulado
                else:
                    parte = r2(m.mora * g.total / base) if base else CERO
                    acumulado += parte
                reparto[g.pk] = parte
            cache[clave] = (m.dias, reparto)
        dias, reparto = cache[clave]
        items.append(ItemLiquidacion(o, dias, reparto.get(o.pk, CERO), o.interes, o.capital))
    return items


def calcular_pago(cuenta, obligacion_ids, fecha_efectiva, ahora=None):
    """Liquida las obligaciones elegidas a la fecha efectiva: mora + interés + capital."""
    ahora = _ahora(ahora)
    if not obligacion_ids:
        raise ErrorNegocio("Selecciona al menos una obligación a pagar.")
    if fecha_efectiva is None:
        raise ErrorNegocio("Indica la fecha efectiva del pago.")
    if fecha_efectiva > timezone.localtime(ahora).date():
        raise ErrorNegocio(f"La fecha de pago ({fecha_efectiva:%d/%m/%Y}) no puede ser futura.")
    ids = {str(i) for i in obligacion_ids}
    obligaciones = list(
        Obligacion.objects.filter(cuenta=cuenta, pk__in=ids)
        .select_related("compra", "compra__condicion")
        .order_by("vencimiento", "compra__numero", "numero")
    )
    if len(obligaciones) != len(ids):
        raise ErrorNegocio("Una de las obligaciones no pertenece a esta cuenta.")
    for o in obligaciones:
        if o.estado != Obligacion.Estado.PENDIENTE:
            if o.estado == Obligacion.Estado.ANULADA:
                raise ErrorNegocio(f"{o} pertenece a una venta anulada; no se cobra.")
            raise ErrorNegocio(f"{o} ya está pagada.")
        if fecha_efectiva < timezone.localtime(o.compra.fecha_compra).date():
            raise ErrorNegocio(f"La fecha de pago no puede ser anterior a la compra N° {o.compra.numero}.")
        # Dentro de una compra en cuotas, se paga en orden: no se salta una cuota anterior.
        anterior = Obligacion.objects.filter(
            compra=o.compra, numero__lt=o.numero, estado=Obligacion.Estado.PENDIENTE
        ).exclude(pk__in=ids).order_by("numero").first()
        if anterior:
            raise ErrorNegocio(f"Primero debe pagarse la cuota {anterior.numero} de la compra N° {o.compra.numero}.")
    return Liquidacion(cuenta, fecha_efectiva, _liquidar(cuenta, obligaciones, fecha_efectiva))


def registrar_pago(usuario, tienda, cuenta_id, obligacion_ids, fecha_efectiva, importe, clave,
                   request=None, ahora=None):
    """Registra un pago íntegro (RN07) y lo aplica en orden mora → interés → capital."""
    cuenta = obtener_cuenta(tienda, cuenta_id, usuario, request)
    previo = Pago.objects.filter(tienda=tienda, clave_idempotencia=clave).first()
    if previo:
        return previo
    try:
        with transaction.atomic():
            Tienda.objects.select_for_update().get(pk=tienda.pk)
            cuenta = CuentaCliente.objects.select_for_update().get(pk=cuenta.pk)
            list(Obligacion.objects.select_for_update().filter(cuenta=cuenta, pk__in=list(obligacion_ids or [])))
            liq = calcular_pago(cuenta, obligacion_ids, fecha_efectiva, ahora)
            try:
                recibido = r2(fin.D(str(importe)))
            except Exception:
                raise ErrorNegocio("Importe inválido: escribe el monto con punto decimal, por ejemplo 201.98.")
            if recibido != liq.total:
                raise ErrorNegocio(
                    f"Pago rechazado: el total a pagar es {_soles(cuenta, liq.total)} y se recibió {_soles(cuenta, recibido)}. "
                    "No se aceptan pagos parciales ni montos distintos (RN07).",
                    {"total": str(liq.total), "recibido": str(recibido)},
                )
            pago = Pago.objects.create(
                tienda=tienda, numero=siguiente_numero(Pago.objects.filter(tienda=tienda)), cuenta=cuenta,
                moneda=cuenta.moneda, fecha_efectiva=fecha_efectiva, mora=liq.mora, interes=liq.interes,
                capital=liq.capital, total=liq.total, clave_idempotencia=clave, registrado_por=usuario,
            )
            PagoAplicacion.objects.bulk_create([
                PagoAplicacion(pago=pago, obligacion=it.obligacion, dias_mora=it.dias_mora, mora=it.mora,
                               interes=it.interes, capital=it.capital, total=it.total)
                for it in liq.items
            ])
            for it in liq.items:
                it.obligacion.estado = Obligacion.Estado.PAGADA
                it.obligacion.pagada_en = fecha_efectiva
                it.obligacion.save(update_fields=["estado", "pagada_en"])
            Auditoria.registrar(
                Auditoria.Evento.PAGO,
                f"Comprobante N° {pago.numero:06d} de {cuenta.codigo}: {_soles(cuenta, pago.total)} "
                f"(mora {pago.mora}, interés {pago.interes}, capital {pago.capital}).",
                usuario=usuario, tienda=tienda, objeto=pago,
                datos={"total": str(pago.total), "mora": str(pago.mora), "obligaciones": len(liq.items)},
                request=request,
            )
            return pago
    except ErrorNegocio as e:
        Auditoria.registrar(
            Auditoria.Evento.PAGO_RECHAZADO, f"Pago rechazado en {cuenta.codigo}: {e.mensaje}"[:300],
            usuario=usuario, tienda=tienda, objeto=cuenta, datos={"motivo": e.mensaje, **e.datos}, request=request,
        )
        raise
    except IntegrityError:
        previo = Pago.objects.filter(tienda=tienda, clave_idempotencia=clave).first()
        if previo:
            return previo
        raise


# ---------------------------------------------------------------------------
# Flujo de cobranzas proyectado (logro del curso: proyección del flujo de caja)
# ---------------------------------------------------------------------------

def flujo_cobranzas(tienda, hoy=None, meses=6):
    """Cobros esperados por mes según los vencimientos pendientes, separados por moneda.

    Devuelve {moneda: [ {"etiqueta", "mes", "capital", "interes", "total", "cantidad"} ... ]}.
    La primera fila agrupa lo ya vencido; luego un renglón por cada uno de los `meses`
    siguientes y, al final, lo que vence después.
    """
    hoy = hoy or timezone.localdate()
    pendientes = Obligacion.objects.filter(tienda=tienda, estado=Obligacion.Estado.PENDIENTE).select_related("cuenta")
    resultado = defaultdict(OrderedDict)

    def fila(moneda, clave, etiqueta, mes=None):
        tabla = resultado[moneda]
        if clave not in tabla:
            tabla[clave] = {"etiqueta": etiqueta, "mes": mes, "vencido": clave == "vencido",
                            "capital": CERO, "interes": CERO, "total": CERO, "cantidad": 0}
        return tabla[clave]

    for moneda in {o.cuenta.moneda for o in pendientes}:
        fila(moneda, "vencido", "Vencido (por cobrar)")
        for k in range(meses):
            m = fin.sumar_meses(date(hoy.year, hoy.month, 1), k)
            fila(moneda, (m.year, m.month), f"{m:%m/%Y}", m)
        fila(moneda, "despues", "Meses posteriores")
    limite = fin.sumar_meses(date(hoy.year, hoy.month, 1), meses)
    for o in pendientes:
        if o.vencimiento < hoy:
            f_ = fila(o.cuenta.moneda, "vencido", "")
        elif o.vencimiento >= limite:
            f_ = fila(o.cuenta.moneda, "despues", "")
        else:
            f_ = fila(o.cuenta.moneda, (o.vencimiento.year, o.vencimiento.month), "")
        f_["capital"] += o.capital
        f_["interes"] += o.interes
        f_["total"] += o.total
        f_["cantidad"] += 1
    return {moneda: list(tabla.values()) for moneda, tabla in resultado.items()}


# ---------------------------------------------------------------------------
# Indicadores de cartera (ajuste B; apartado 2.6 del informe)
# ---------------------------------------------------------------------------

DIAS_VENTAS_PPC = 90


def indicadores_cartera(tienda, hoy=None):
    """Indicadores por moneda para el panel del negocio.

    - Capital por cobrar = Σ capital pendiente  → capital de trabajo inmovilizado en cuentas por cobrar.
    - Total por cobrar   = Σ (capital + interés) pendiente.
    - Vencido            = Σ total pendiente con vencimiento anterior a hoy.
    - Índice de morosidad = Vencido / Total por cobrar.
    - Cobrado del mes    = Σ pagos con fecha efectiva en el mes actual.
    - Periodo promedio de cobro (días) = Capital por cobrar / Ventas al crédito de los últimos 90 días × 90.
    """
    hoy = hoy or timezone.localdate()
    inicio_mes = date(hoy.year, hoy.month, 1)
    desde_ventas = timezone.make_aware(datetime.combine(hoy, datetime.min.time())) - timedelta(days=DIAS_VENTAS_PPC)
    monedas = set(CuentaCliente.objects.filter(tienda=tienda).values_list("moneda", flat=True))
    salida = {}
    for moneda in sorted(monedas):
        pend = Obligacion.objects.filter(tienda=tienda, cuenta__moneda=moneda, estado=Obligacion.Estado.PENDIENTE)
        agg = pend.aggregate(capital=Sum("capital"), total=Sum("total"))
        capital, total = r2(agg["capital"] or CERO), r2(agg["total"] or CERO)
        vencidas = pend.filter(vencimiento__lt=hoy)
        vencido = r2(vencidas.aggregate(s=Sum("total"))["s"] or CERO)
        cobrado = r2(Pago.objects.filter(tienda=tienda, moneda=moneda, fecha_efectiva__gte=inicio_mes,
                                         fecha_efectiva__lte=hoy, anulado=False).aggregate(s=Sum("total"))["s"] or CERO)
        ventas = r2(Compra.objects.filter(tienda=tienda, moneda=moneda, fecha_compra__gte=desde_ventas, anulada=False)
                    .aggregate(s=Sum("capital"))["s"] or CERO)
        salida[moneda] = {
            "capital": capital,
            "total": total,
            "interes": total - capital,
            "vencido": vencido,
            "morosidad": (vencido / total) if total else CERO,
            "cobrado_mes": cobrado,
            "ventas_90": ventas,
            "ppc_dias": (capital / ventas * DIAS_VENTAS_PPC).quantize(Decimal("1")) if ventas else None,
            "clientes_con_deuda": pend.values("cuenta").distinct().count(),
            "clientes_en_mora": vencidas.values("cuenta").distinct().count(),
        }
    return salida


# ---------------------------------------------------------------------------
# Anulaciones: corrección trazable de errores de registro (sección 5.3 del informe)
# ---------------------------------------------------------------------------

MOTIVO_MINIMO = 10


def _validar_motivo(motivo):
    motivo = (motivo or "").strip()
    if len(motivo) < MOTIVO_MINIMO:
        raise ErrorNegocio(f"Explica el motivo de la anulación (mínimo {MOTIVO_MINIMO} caracteres).")
    return motivo[:300]


def por_que_no_anular_compra(compra):
    """None si la venta puede anularse; si no, el motivo en texto."""
    if compra.anulada:
        return "La venta ya está anulada."
    if compra.obligaciones.filter(estado=Obligacion.Estado.PAGADA).exists():
        return "Tiene obligaciones pagadas: primero anula esos pagos (del más reciente al más antiguo)."
    return None


def por_que_no_anular_pago(pago):
    """None si el pago puede anularse. Solo se anula el último pago vigente de la cuenta (orden inverso)."""
    if pago.anulado:
        return "El pago ya está anulado."
    ultimo = Pago.objects.filter(cuenta_id=pago.cuenta_id, anulado=False).order_by("-registrado_en", "-numero").first()
    if ultimo and ultimo.pk != pago.pk:
        return f"Solo se puede anular el último pago de la cuenta (comprobante {ultimo.numero:06d}); se anulan en orden inverso."
    return None


def _obtener_de_tienda(modelo, tienda, objeto_id, usuario, request):
    try:
        return modelo.objects.select_related("cuenta").get(pk=objeto_id, tienda=tienda)
    except (modelo.DoesNotExist, ValidationError, ValueError):
        Auditoria.registrar(
            Auditoria.Evento.ACCESO_DENEGADO,
            f"Intento de anular {modelo._meta.verbose_name} {objeto_id} fuera de la tienda {tienda.codigo}.",
            usuario=usuario, tienda=tienda, datos={"id": str(objeto_id)}, request=request,
        )
        raise Http404("No encontrado en esta tienda.")


def anular_compra(usuario, tienda, compra_id, motivo, request=None):
    """Anula una venta sin pagos: sus obligaciones quedan ANULADA y el crédito se libera (RN06, RN09)."""
    compra = _obtener_de_tienda(Compra, tienda, compra_id, usuario, request)
    motivo = _validar_motivo(motivo)
    with transaction.atomic():
        CuentaCliente.objects.select_for_update().get(pk=compra.cuenta_id)
        compra = Compra.objects.select_for_update().get(pk=compra.pk)
        problema = por_que_no_anular_compra(compra)
        if problema:
            raise ErrorNegocio(problema)
        anulacion = Anulacion.objects.create(
            tienda=tienda, tipo=Anulacion.Tipo.COMPRA, compra=compra, motivo=motivo, registrada_por=usuario
        )
        compra.anulada = True
        compra.save(update_fields=["anulada"])
        for o in compra.obligaciones.select_for_update().filter(estado=Obligacion.Estado.PENDIENTE):
            o.estado = Obligacion.Estado.ANULADA
            o.save(update_fields=["estado"])
        Auditoria.registrar(
            Auditoria.Evento.ANULACION,
            f"Venta N° {compra.numero} de {compra.cuenta.codigo} anulada ({_soles(compra.cuenta, compra.capital)}): {motivo}"[:300],
            usuario=usuario, tienda=tienda, objeto=anulacion, datos={"compra": str(compra.pk), "motivo": motivo},
            request=request,
        )
    return anulacion


def anular_pago(usuario, tienda, pago_id, motivo, request=None):
    """Anula el último pago de una cuenta: sus obligaciones vuelven a PENDIENTE y pueden cobrarse otra vez."""
    pago = _obtener_de_tienda(Pago, tienda, pago_id, usuario, request)
    motivo = _validar_motivo(motivo)
    with transaction.atomic():
        CuentaCliente.objects.select_for_update().get(pk=pago.cuenta_id)
        pago = Pago.objects.select_for_update().get(pk=pago.pk)
        problema = por_que_no_anular_pago(pago)
        if problema:
            raise ErrorNegocio(problema)
        anulacion = Anulacion.objects.create(
            tienda=tienda, tipo=Anulacion.Tipo.PAGO, pago=pago, motivo=motivo, registrada_por=usuario
        )
        pago.anulado = True
        pago.save(update_fields=["anulado"])
        for aplicacion in pago.aplicaciones.select_related("obligacion"):
            aplicacion.anulada = True
            aplicacion.save(update_fields=["anulada"])
            o = aplicacion.obligacion
            o.estado, o.pagada_en = Obligacion.Estado.PENDIENTE, None
            o.save(update_fields=["estado", "pagada_en"])
        Auditoria.registrar(
            Auditoria.Evento.ANULACION,
            f"Comprobante N° {pago.numero:06d} de {pago.cuenta.codigo} anulado ({_soles(pago.cuenta, pago.total)}): {motivo}"[:300],
            usuario=usuario, tienda=tienda, objeto=anulacion, datos={"pago": str(pago.pk), "motivo": motivo},
            request=request,
        )
    return anulacion
