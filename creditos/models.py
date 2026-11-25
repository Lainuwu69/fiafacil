"""
Modelos financieros de FíaFácil (capítulo 5 del informe, submodelo de operaciones).

Flujo: una Compra (con sus líneas DetalleCompra) genera una Obligacion (pago a
fin de mes) o n Obligaciones (cuotas francesas). En la fecha de corte se genera
un EstadoCuenta con sus líneas EstadoDetalle. Un Pago cancela íntegramente una
o varias obligaciones; cada PagoAplicacion registra cuánto fue a mora, interés
y capital (prelación del Anexo A).

Todos son registros inmutables (RN09, RN10): no se borran ni se reescriben.
La única excepción es el estado de una obligación cuando se paga.
"""

import uuid

from django.conf import settings
from django.db import models
from django.db.models import F, Q

from core.campos import cantidad, importe, tasa
from core.constantes import Moneda, Modalidad
from core.modelos_base import RegistroInmutable

TIENDA_HELP = "Tienda a la que pertenece el registro; se valida en el servidor (RN01)."


class Compra(RegistroInmutable):
    """Venta al crédito. Copia la versión de condiciones vigente al momento de la compra (RN10)."""

    # Lo único que cambia después de registrada: la marca de anulación (ver Anulacion).
    campos_actualizables = ("anulada",)

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tienda = models.ForeignKey("tiendas.Tienda", on_delete=models.PROTECT, related_name="compras", help_text=TIENDA_HELP)
    numero = models.PositiveIntegerField("número", help_text="Correlativo de la compra dentro de la tienda.")
    cuenta = models.ForeignKey(
        "clientes.CuentaCliente", on_delete=models.PROTECT, related_name="compras", help_text="Cuenta del cliente que compra."
    )
    condicion = models.ForeignKey(
        "clientes.CondicionCredito",
        on_delete=models.PROTECT,
        related_name="compras",
        help_text="Versión de condiciones con la que se calculó la compra (RN10).",
    )
    moneda = models.CharField("moneda", max_length=3, choices=Moneda.choices, help_text="Moneda de la cuenta (RN02).")
    fecha_compra = models.DateTimeField(
        "fecha y hora de la compra",
        help_text="Momento de la venta (hora de Lima). Puede ser pasado, para pasar fiados del cuaderno, pero nunca futuro.",
    )
    modalidad = models.CharField(
        "modalidad", max_length=7, choices=Modalidad.choices, help_text="Pago a fin de mes o en cuotas (RN05)."
    )
    n_cuotas = models.PositiveSmallIntegerField(
        "número de cuotas", null=True, blank=True, help_text="Solo en cuotas: entre 1 y el máximo pactado."
    )
    capital = importe("capital", "Suma de las líneas: cantidad × precio de lista, cada una redondeada a 2 decimales.")
    corte = models.DateTimeField(
        "corte asignado", help_text="Primer corte estrictamente posterior a la compra (RN03)."
    )
    fecha_pago = models.DateField(
        "fecha de pago del ciclo", help_text="Vencimiento del pago mensual o fin de la gracia en cuotas (G)."
    )
    dias = models.PositiveIntegerField(
        "días financiados", help_text="Días exactos desde la compra hasta la fecha de pago del ciclo (sin contar el primero)."
    )
    tasa_periodo = tasa(
        "tasa del periodo",
        "Tasa efectiva aplicada: i(días) en pago mensual o TEM en cuotas, con 15 decimales.",
    )
    interes = importe(
        "interés compensatorio",
        "Pago mensual: interés hasta el vencimiento. Cuotas: suma de intereses del cronograma.",
    )
    capital_con_gracia = importe(
        "capital después de la gracia", "Solo en cuotas: Pg = capital × (1 + TEM)^(g/30).", null=True, blank=True
    )
    cuota = importe("cuota", "Solo en cuotas: cuota francesa constante (la última puede ajustarse).", null=True, blank=True)
    total = importe("total a pagar", "Capital + intereses (incluye la gracia capitalizada en cuotas).")
    tcea = tasa(
        "TCEA",
        "Tasa de costo efectivo anual de la compra: TIR de sus flujos expresada en 360 días.",
        null=True,
        blank=True,
    )
    tcea_contado = tasa(
        "TCEA sobre precio contado",
        "TCEA tomando como valor recibido el precio contado; incluye el sobreprecio de lista.",
        null=True,
        blank=True,
    )
    clave_idempotencia = models.UUIDField(
        "clave de idempotencia", help_text="Identifica la solicitud; si llega dos veces, no se registra dos veces."
    )
    registrada_en = models.DateTimeField(
        "registrada en", auto_now_add=True, help_text="Momento real en que se grabó en el sistema."
    )
    registrada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", help_text="Usuario del negocio que registró la venta."
    )
    anulada = models.BooleanField(
        "anulada", default=False,
        help_text="Marcada si la venta se anuló por un error de registro; el detalle está en la tabla de anulaciones (RN09).",
    )

    class Meta:
        db_table = "compra"
        verbose_name = "compra"
        verbose_name_plural = "compras"
        ordering = ["fecha_compra", "numero"]
        constraints = [
            models.UniqueConstraint(fields=["tienda", "numero"], name="uq_compra_tienda_numero"),
            models.UniqueConstraint(fields=["tienda", "clave_idempotencia"], name="uq_compra_idempotencia"),
            models.CheckConstraint(condition=Q(capital__gt=0), name="ck_compra_capital_positivo"),
            models.CheckConstraint(condition=Q(interes__gte=0), name="ck_compra_interes_no_negativo"),
            models.CheckConstraint(condition=Q(tasa_periodo__gte=0), name="ck_compra_tasa_no_negativa"),
            models.CheckConstraint(condition=Q(moneda__in=["PEN", "USD"]), name="ck_compra_moneda"),
            models.CheckConstraint(
                condition=Q(modalidad="MENSUAL", n_cuotas__isnull=True, capital_con_gracia__isnull=True, cuota__isnull=True)
                | Q(modalidad="CUOTAS", n_cuotas__gte=1, capital_con_gracia__isnull=False, cuota__isnull=False),
                name="ck_compra_modalidad_coherente",
            ),
            models.CheckConstraint(condition=Q(corte__gt=F("fecha_compra")), name="ck_compra_corte_posterior"),
        ]
        indexes = [models.Index(fields=["cuenta", "fecha_compra"], name="ix_compra_cuenta_fecha")]

    def __str__(self):
        return f"Compra {self.numero} · {self.cuenta}"


class DetalleCompra(RegistroInmutable):
    """Línea de una compra. Copia descripción, unidad y precios aunque luego cambie el catálogo."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    compra = models.ForeignKey(Compra, on_delete=models.PROTECT, related_name="detalles", help_text="Compra a la que pertenece.")
    linea = models.PositiveSmallIntegerField("línea", help_text="Orden de la línea dentro de la compra.")
    articulo = models.ForeignKey(
        "tiendas.Articulo", on_delete=models.PROTECT, related_name="+", help_text="Artículo vendido."
    )
    descripcion = models.CharField("descripción", max_length=200, help_text="Descripción copiada del artículo.")
    unidad = models.CharField("unidad", max_length=20, help_text="Unidad de medida copiada del artículo.")
    cantidad = cantidad("cantidad", "Unidades vendidas (hasta 3 decimales). Ej.: 1.250 kg.")
    precio_unitario = importe("precio de lista unitario", "Precio de crédito copiado del catálogo el día de la venta.")
    precio_contado = importe("precio contado unitario", "Precio contado copiado, para calcular la TCEA sobre contado.")
    importe = importe("importe", "cantidad × precio de lista, redondeado a 2 decimales.")

    class Meta:
        db_table = "detalle_compra"
        verbose_name = "detalle de compra"
        verbose_name_plural = "detalles de compra"
        ordering = ["compra", "linea"]
        constraints = [
            models.UniqueConstraint(fields=["compra", "linea"], name="uq_detalle_compra_linea"),
            models.CheckConstraint(condition=Q(cantidad__gt=0), name="ck_detalle_cantidad_positiva"),
            models.CheckConstraint(condition=Q(precio_unitario__gt=0), name="ck_detalle_precio_positivo"),
            models.CheckConstraint(condition=Q(importe__gt=0), name="ck_detalle_importe_positivo"),
        ]

    def __str__(self):
        return f"{self.cantidad} × {self.descripcion}"


class Obligacion(RegistroInmutable):
    """Lo que el cliente debe pagar en una fecha: el pago mensual de una compra o una cuota."""

    campos_actualizables = ("estado", "pagada_en")

    class Tipo(models.TextChoices):
        MENSUAL = "MENSUAL", "Pago a fin de mes"
        CUOTA = "CUOTA", "Cuota"

    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        PAGADA = "PAGADA", "Pagada"
        ANULADA = "ANULADA", "Anulada"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tienda = models.ForeignKey("tiendas.Tienda", on_delete=models.PROTECT, related_name="obligaciones", help_text=TIENDA_HELP)
    cuenta = models.ForeignKey(
        "clientes.CuentaCliente", on_delete=models.PROTECT, related_name="obligaciones", help_text="Cuenta deudora."
    )
    compra = models.ForeignKey(Compra, on_delete=models.PROTECT, related_name="obligaciones", help_text="Compra que la originó.")
    numero = models.PositiveSmallIntegerField("número", help_text="1 en pago mensual; k en la cuota k del cronograma.")
    tipo = models.CharField("tipo", max_length=7, choices=Tipo.choices, help_text="Pago mensual o cuota.")
    corte = models.DateTimeField(
        "corte del ciclo", help_text="Corte del ciclo al que pertenece; agrupa la obligación en el estado de cuenta."
    )
    vencimiento = models.DateField("vencimiento", help_text="Fecha en que debe pagarse íntegramente.")
    saldo_inicial = importe("saldo inicial", "Solo cuotas: saldo antes de esta cuota (Sₖ₋₁).", null=True, blank=True)
    capital = importe("capital", "Pago mensual: capital de la compra. Cuota: amortización Aₖ.")
    interes = importe("interés", "Interés compensatorio de la obligación (Iₖ en cuotas).")
    total = importe("total", "capital + interés: importe que debe pagarse en el vencimiento (V).")
    saldo_final = importe("saldo final", "Solo cuotas: saldo del plan después de esta cuota (Sₖ).", null=True, blank=True)
    estado = models.CharField(
        "estado", max_length=9, choices=Estado.choices, default=Estado.PENDIENTE, help_text="Pendiente hasta que se cancela íntegra."
    )
    pagada_en = models.DateField("pagada el", null=True, blank=True, help_text="Fecha efectiva del pago que la canceló.")

    class Meta:
        db_table = "obligacion"
        verbose_name = "obligación"
        verbose_name_plural = "obligaciones"
        ordering = ["vencimiento", "compra__numero", "numero"]
        constraints = [
            models.UniqueConstraint(fields=["compra", "numero"], name="uq_obligacion_compra_numero"),
            models.CheckConstraint(condition=Q(capital__gte=0), name="ck_obligacion_capital_no_negativo"),
            models.CheckConstraint(condition=Q(interes__gte=0), name="ck_obligacion_interes_no_negativo"),
            models.CheckConstraint(condition=Q(total=F("capital") + F("interes")), name="ck_obligacion_total"),
            models.CheckConstraint(condition=Q(saldo_final__isnull=True) | Q(saldo_final__gte=0), name="ck_obligacion_saldo"),
            models.CheckConstraint(
                condition=Q(estado__in=["PENDIENTE", "ANULADA"], pagada_en__isnull=True) | Q(estado="PAGADA", pagada_en__isnull=False),
                name="ck_obligacion_estado_coherente",
            ),
        ]
        indexes = [models.Index(fields=["cuenta", "estado", "vencimiento"], name="ix_obligacion_cuenta_estado")]

    def __str__(self):
        etiqueta = "Pago mensual" if self.tipo == self.Tipo.MENSUAL else f"Cuota {self.numero}"
        return f"{etiqueta} · compra {self.compra.numero} · vence {self.vencimiento:%d/%m/%Y}"


class EstadoCuenta(RegistroInmutable):
    """Listado de pago generado en la fecha de corte (requisito 6). Sus totales quedan congelados."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tienda = models.ForeignKey("tiendas.Tienda", on_delete=models.PROTECT, related_name="estados", help_text=TIENDA_HELP)
    cuenta = models.ForeignKey(
        "clientes.CuentaCliente", on_delete=models.PROTECT, related_name="estados", help_text="Cuenta del estado."
    )
    corte = models.DateTimeField("corte", help_text="Fecha y hora del corte del ciclo.")
    fecha_pago = models.DateField("fecha de pago", help_text="Fecha en que el cliente debe pagar el total del estado.")
    capital = importe("capital", "Suma del capital de las líneas del estado.")
    interes = importe("interés", "Suma de los intereses compensatorios de las líneas.")
    total = importe("total a pagar", "Capital + interés a pagar en la fecha de pago (sin mora).")
    generado_en = models.DateTimeField("generado en", auto_now_add=True, help_text="Momento en que se generó.")
    generado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        help_text="Usuario que lo generó; vacío si lo generó el proceso automático diario.",
    )

    class Meta:
        db_table = "estado_cuenta"
        verbose_name = "estado de cuenta"
        verbose_name_plural = "estados de cuenta"
        ordering = ["cuenta", "-corte"]
        constraints = [
            models.UniqueConstraint(fields=["cuenta", "corte"], name="uq_estado_cuenta_corte"),
            models.CheckConstraint(condition=Q(total=F("capital") + F("interes")), name="ck_estado_total"),
            models.CheckConstraint(condition=Q(capital__gte=0, interes__gte=0), name="ck_estado_no_negativo"),
        ]

    def __str__(self):
        return f"Estado {self.cuenta} · corte {self.corte:%d/%m/%Y}"


class EstadoDetalle(RegistroInmutable):
    """Línea congelada de un estado de cuenta: una obligación con sus importes al corte."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    estado = models.ForeignKey(EstadoCuenta, on_delete=models.PROTECT, related_name="detalles", help_text="Estado al que pertenece.")
    obligacion = models.ForeignKey(
        Obligacion, on_delete=models.PROTECT, related_name="lineas_estado", help_text="Obligación incluida."
    )
    orden = models.PositiveSmallIntegerField("orden", help_text="Posición en el listado, por fecha de compra.")
    fecha_compra = models.DateTimeField("fecha de compra", help_text="Fecha y hora de la compra que originó la línea.")
    descripcion = models.CharField("descripción", max_length=200, help_text="Texto mostrado. Ej.: Compra 3 o Cuota 1/3 de la compra 2.")
    dias = models.PositiveIntegerField("días", null=True, blank=True, help_text="Días financiados (solo pago mensual).")
    capital = importe("capital", "Capital de la línea.")
    interes = importe("interés", "Interés compensatorio de la línea.")
    total = importe("total", "Capital + interés de la línea.")

    class Meta:
        db_table = "estado_detalle"
        verbose_name = "línea de estado de cuenta"
        verbose_name_plural = "líneas de estado de cuenta"
        ordering = ["estado", "orden"]
        constraints = [
            models.UniqueConstraint(fields=["estado", "obligacion"], name="uq_estado_detalle_obligacion"),
            models.CheckConstraint(condition=Q(total=F("capital") + F("interes")), name="ck_estado_detalle_total"),
        ]

    def __str__(self):
        return f"{self.orden}. {self.descripcion}"


class Pago(RegistroInmutable):
    """Cobro que cancela íntegramente una o varias obligaciones (RN07). Es el comprobante."""

    campos_actualizables = ("anulado",)

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tienda = models.ForeignKey("tiendas.Tienda", on_delete=models.PROTECT, related_name="pagos", help_text=TIENDA_HELP)
    numero = models.PositiveIntegerField("número de comprobante", help_text="Correlativo del comprobante dentro de la tienda.")
    cuenta = models.ForeignKey("clientes.CuentaCliente", on_delete=models.PROTECT, related_name="pagos", help_text="Cuenta que paga.")
    moneda = models.CharField("moneda", max_length=3, choices=Moneda.choices, help_text="Moneda de la cuenta (RN02).")
    fecha_efectiva = models.DateField(
        "fecha efectiva de pago", help_text="Día en que el cliente pagó; define los días de mora. No puede ser futura."
    )
    mora = importe("mora", "Total aplicado a intereses moratorios (primero en la prelación).")
    interes = importe("interés", "Total aplicado a intereses compensatorios.")
    capital = importe("capital", "Total aplicado a capital; libera crédito disponible.")
    total = importe("total pagado", "Importe exacto recibido: mora + interés + capital. No se aceptan pagos parciales.")
    clave_idempotencia = models.UUIDField(
        "clave de idempotencia", help_text="Identifica la solicitud; si llega dos veces, no se cobra dos veces."
    )
    registrado_en = models.DateTimeField("registrado en", auto_now_add=True, help_text="Momento real del registro.")
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", help_text="Usuario del negocio que registró el pago."
    )
    anulado = models.BooleanField(
        "anulado", default=False,
        help_text="Marcado si el pago se anuló por un error de registro; sus obligaciones vuelven a quedar pendientes.",
    )

    class Meta:
        db_table = "pago"
        verbose_name = "pago"
        verbose_name_plural = "pagos"
        ordering = ["-fecha_efectiva", "-numero"]
        constraints = [
            models.UniqueConstraint(fields=["tienda", "numero"], name="uq_pago_tienda_numero"),
            models.UniqueConstraint(fields=["tienda", "clave_idempotencia"], name="uq_pago_idempotencia"),
            models.CheckConstraint(condition=Q(total__gt=0), name="ck_pago_total_positivo"),
            models.CheckConstraint(condition=Q(mora__gte=0, interes__gte=0, capital__gte=0), name="ck_pago_componentes"),
            models.CheckConstraint(condition=Q(total=F("mora") + F("interes") + F("capital")), name="ck_pago_total"),
            models.CheckConstraint(condition=Q(moneda__in=["PEN", "USD"]), name="ck_pago_moneda"),
        ]

    def __str__(self):
        return f"Comprobante {self.numero:06d} · {self.cuenta}"


class PagoAplicacion(RegistroInmutable):
    """Cómo se aplicó un pago a una obligación: mora → interés → capital (Anexo A)."""

    campos_actualizables = ("anulada",)

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pago = models.ForeignKey(Pago, on_delete=models.PROTECT, related_name="aplicaciones", help_text="Pago aplicado.")
    obligacion = models.ForeignKey(
        Obligacion, on_delete=models.PROTECT, related_name="aplicaciones", help_text="Obligación cancelada."
    )
    dias_mora = models.PositiveIntegerField("días de mora", help_text="Días exactos desde el vencimiento hasta la fecha efectiva.")
    mora = importe("mora", "M = V × iₘ(días de mora), redondeado a 2 decimales (RN08).")
    interes = importe("interés", "Interés compensatorio cancelado.")
    capital = importe("capital", "Capital cancelado.")
    total = importe("total", "mora + interés + capital de esta obligación.")
    anulada = models.BooleanField(
        "anulada", default=False, help_text="Marcada cuando se anula el pago al que pertenece."
    )

    class Meta:
        db_table = "pago_aplicacion"
        verbose_name = "aplicación de pago"
        verbose_name_plural = "aplicaciones de pago"
        constraints = [
            # Una obligación solo puede tener UNA aplicación vigente: impide cobros duplicados.
            # Si el pago se anula, la obligación vuelve a pendiente y puede cobrarse de nuevo.
            models.UniqueConstraint(
                fields=["obligacion"], condition=Q(anulada=False), name="uq_aplicacion_obligacion_una_vez"
            ),
            models.CheckConstraint(condition=Q(mora__gte=0, interes__gte=0, capital__gte=0), name="ck_aplicacion_componentes"),
            models.CheckConstraint(condition=Q(total=F("mora") + F("interes") + F("capital")), name="ck_aplicacion_total"),
        ]

    def __str__(self):
        return f"{self.pago} → {self.obligacion}"


class Anulacion(RegistroInmutable):
    """Corrección de un error de registro (sección 5.3 del informe): un evento trazable, no un borrado.

    Anular una VENTA (solo si ninguna de sus obligaciones fue pagada) deja sus obligaciones en
    estado ANULADA y libera el crédito. Anular un PAGO (solo el último de la cuenta) devuelve
    sus obligaciones a PENDIENTE. Los registros originales se conservan (RN09).
    """

    class Tipo(models.TextChoices):
        COMPRA = "COMPRA", "Venta"
        PAGO = "PAGO", "Pago"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tienda = models.ForeignKey("tiendas.Tienda", on_delete=models.PROTECT, related_name="anulaciones", help_text=TIENDA_HELP)
    tipo = models.CharField("tipo", max_length=6, choices=Tipo.choices, help_text="Qué se anuló: una venta o un pago.")
    compra = models.ForeignKey(
        Compra, on_delete=models.PROTECT, null=True, blank=True, related_name="anulaciones", help_text="Venta anulada."
    )
    pago = models.ForeignKey(Pago, on_delete=models.PROTECT, null=True, blank=True, related_name="anulaciones", help_text="Pago anulado.")
    motivo = models.CharField(
        "motivo", max_length=300,
        help_text="Explica el error que se corrige (mínimo 10 caracteres). Ej.: Se registró 120 en vez de 12.",
    )
    registrada_en = models.DateTimeField("registrada en", auto_now_add=True, help_text="Momento de la anulación.")
    registrada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", help_text="Usuario del negocio que anuló."
    )

    class Meta:
        db_table = "anulacion"
        verbose_name = "anulación"
        verbose_name_plural = "anulaciones"
        ordering = ["-registrada_en"]
        constraints = [
            models.CheckConstraint(
                condition=Q(tipo="COMPRA", compra__isnull=False, pago__isnull=True)
                | Q(tipo="PAGO", pago__isnull=False, compra__isnull=True),
                name="ck_anulacion_un_objeto",
            ),
            # Cada venta o pago se anula una sola vez.
            models.UniqueConstraint(fields=["compra"], condition=Q(compra__isnull=False), name="uq_anulacion_compra"),
            models.UniqueConstraint(fields=["pago"], condition=Q(pago__isnull=False), name="uq_anulacion_pago"),
        ]

    def __str__(self):
        objeto = f"venta N° {self.compra.numero}" if self.compra_id else f"comprobante {self.pago.numero:06d}"
        return f"Anulación de {objeto}"
