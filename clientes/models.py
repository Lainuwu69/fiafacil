"""
Modelos de la app clientes (capítulo 5 del informe).

- CuentaCliente: cuenta corriente de un vecino en una tienda y una moneda (RN02).
- CondicionCredito: tasas, límite, plazo, corte y pago pactados. Se versiona
  (RN10): un cambio crea una versión nueva y las compras anteriores conservan
  la versión con la que se hicieron.
"""

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Cast, Substr
from django.utils import timezone

from core.campos import importe, tasa
from core.constantes import PERIODOS_VALIDOS, Moneda, PeriodoTasa, TipoTasa
from core.modelos_base import RegistroInmutable, SinBorradoFisico, siguiente_numero


class CuentaCliente(SinBorradoFisico):
    """Cuenta corriente de un cliente en una tienda. Un cliente con dos monedas tiene dos cuentas."""

    class TipoDocumento(models.TextChoices):
        DNI = "DNI", "DNI"
        CE = "CE", "Carné de extranjería"
        RUC = "RUC", "RUC"
        PASAPORTE = "PAS", "Pasaporte"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tienda = models.ForeignKey(
        "tiendas.Tienda", on_delete=models.PROTECT, related_name="cuentas", help_text="Tienda que otorga el crédito (RN01)."
    )
    codigo = models.CharField(
        "código", max_length=10, editable=False, help_text="Código correlativo dentro de la tienda, por ejemplo C001."
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="cuentas_cliente",
        help_text="Opcional. Usuario con el que el cliente consulta esta cuenta en el portal.",
    )
    tipo_documento = models.CharField(
        "tipo de documento",
        max_length=3,
        choices=TipoDocumento.choices,
        default=TipoDocumento.DNI,
        help_text="Documento de identidad del cliente.",
    )
    documento = models.CharField(
        "número de documento", max_length=20, help_text="Número del documento sin espacios. Ej.: DNI de 8 dígitos 45678912."
    )
    nombre = models.CharField(
        "nombre completo", max_length=150, help_text="Nombres y apellidos del cliente. Ej.: Carmen Quispe Rojas."
    )
    telefono = models.CharField(
        "teléfono", max_length=20, blank=True, help_text="Opcional. Celular del cliente para coordinar pagos. Ej.: 987654321."
    )
    correo = models.EmailField(
        "correo", max_length=254, blank=True, help_text="Opcional. Correo del cliente. Ej.: carmen@correo.pe."
    )
    direccion = models.CharField(
        "dirección", max_length=200, blank=True, help_text="Opcional. Referencia de su domicilio en la zona."
    )
    moneda = models.CharField(
        "moneda",
        max_length=3,
        choices=Moneda.choices,
        default=Moneda.PEN,
        help_text="Moneda única de la cuenta (RN02). Para otra moneda se abre otra cuenta; no hay tipo de cambio.",
    )
    activo = models.BooleanField(
        "activa", default=True, help_text="Desmárcala para dar de baja la cuenta: no admite compras nuevas y conserva su historial."
    )
    fecha_alta = models.DateTimeField(
        "fecha de alta", default=timezone.now, editable=False, help_text="Momento en que se abrió la cuenta."
    )

    class Meta:
        db_table = "cuenta_cliente"
        verbose_name = "cuenta de cliente"
        verbose_name_plural = "cuentas de clientes"
        ordering = ["tienda", "codigo"]
        constraints = [
            models.UniqueConstraint(fields=["tienda", "documento", "moneda"], name="uq_cuenta_tienda_documento_moneda"),
            models.UniqueConstraint(fields=["tienda", "codigo"], name="uq_cuenta_tienda_codigo"),
            models.CheckConstraint(condition=models.Q(moneda__in=["PEN", "USD"]), name="ck_cuenta_moneda"),
        ]

    def __str__(self):
        return f"{self.codigo} {self.nombre} ({self.moneda})"

    def save(self, *args, **kwargs):
        if not self.codigo:
            n = siguiente_numero(
                CuentaCliente.objects.filter(tienda_id=self.tienda_id, codigo__regex=r"^C[0-9]+$").annotate(
                    n=Cast(Substr("codigo", 2), models.IntegerField())
                ),
                "n",
            )
            self.codigo = f"C{n:03d}"
        super().save(*args, **kwargs)

    def condicion_vigente(self):
        """Versión de condiciones vigente hoy (la que no tiene fecha de fin)."""
        return self.condiciones.filter(vigente_hasta__isnull=True).first()


class CondicionCredito(RegistroInmutable):
    """Condiciones pactadas con el cliente. Inmutable: solo se cierra su vigencia (RN10)."""

    campos_actualizables = ("vigente_hasta",)

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cuenta = models.ForeignKey(
        CuentaCliente, on_delete=models.PROTECT, related_name="condiciones", help_text="Cuenta a la que se aplican las condiciones."
    )
    version = models.PositiveSmallIntegerField(
        "versión", help_text="Número de versión: 1 al abrir la cuenta y +1 en cada cambio de condiciones (RN10)."
    )

    # --- Tasa compensatoria ---
    tasa_tipo = models.CharField(
        "tipo de tasa",
        max_length=8,
        choices=TipoTasa.choices,
        help_text="Efectiva (TEA, TEM…) o nominal (TNA…). La nominal necesita indicar su capitalización.",
    )
    tasa_valor = tasa(
        "tasa compensatoria",
        "Se guarda como decimal: 24 % = 0.24. En pantalla se escribe en porcentaje (24).",
    )
    tasa_periodo = models.PositiveSmallIntegerField(
        "periodo de la tasa",
        choices=PeriodoTasa.choices,
        default=PeriodoTasa.ANUAL,
        help_text="Periodo al que corresponde la tasa. Si no se indica, se asume anual (360 días).",
    )
    tasa_capitalizacion = models.PositiveSmallIntegerField(
        "capitalización",
        choices=PeriodoTasa.choices,
        null=True,
        blank=True,
        help_text="Solo para tasa nominal: cada cuántos días se capitaliza. Si no se indica, se asume diaria (1 día).",
    )

    # --- Tasa moratoria ---
    mora_tipo = models.CharField(
        "tipo de tasa moratoria", max_length=8, choices=TipoTasa.choices, help_text="Efectiva o nominal, igual que la compensatoria."
    )
    mora_valor = tasa("tasa moratoria", "Tasa que se cobra por los días de atraso. Se guarda como decimal: 3 % = 0.03.")
    mora_periodo = models.PositiveSmallIntegerField(
        "periodo de la tasa moratoria",
        choices=PeriodoTasa.choices,
        default=PeriodoTasa.ANUAL,
        help_text="Periodo de la tasa moratoria. Si no se indica, se asume anual (360 días).",
    )
    mora_capitalizacion = models.PositiveSmallIntegerField(
        "capitalización moratoria",
        choices=PeriodoTasa.choices,
        null=True,
        blank=True,
        help_text="Solo si la moratoria es nominal. Si no se indica, se asume diaria (1 día).",
    )

    # --- Límites y calendario ---
    limite = importe("límite de crédito", "Capital máximo que el cliente puede deber al mismo tiempo. Ej.: 1000.00.")
    plazo_max = models.PositiveSmallIntegerField(
        "máximo de cuotas", help_text="Número máximo de meses para comprar en cuotas (1 a 60). Ej.: 3."
    )
    dia_corte = models.PositiveSmallIntegerField(
        "día de corte", help_text="Día del mes en que se cierra el ciclo (1 a 27). Ej.: 20."
    )
    hora_corte = models.TimeField(
        "hora de corte",
        help_text="Hora exacta del corte (hora de Lima). Una compra a esa hora o después pasa al ciclo siguiente (RN03). Ej.: 20:00.",
    )
    dia_pago = models.PositiveSmallIntegerField(
        "día de pago", help_text="Día del mes en que el cliente paga (2 a 28), siempre después del día de corte. Ej.: 26."
    )

    # --- Vigencia ---
    vigente_desde = models.DateTimeField(
        "vigente desde", default=timezone.now, help_text="Momento desde el que rigen estas condiciones."
    )
    vigente_hasta = models.DateTimeField(
        "vigente hasta", null=True, blank=True, help_text="Momento en que fueron reemplazadas por una versión nueva."
    )
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        help_text="Usuario del negocio que registró esta versión.",
    )

    class Meta:
        db_table = "condicion_credito"
        verbose_name = "condición de crédito"
        verbose_name_plural = "condiciones de crédito"
        ordering = ["cuenta", "-version"]
        constraints = [
            models.UniqueConstraint(fields=["cuenta", "version"], name="uq_condicion_cuenta_version"),
            models.UniqueConstraint(
                fields=["cuenta"], condition=models.Q(vigente_hasta__isnull=True), name="uq_condicion_una_vigente"
            ),
            models.CheckConstraint(condition=models.Q(tasa_valor__gte=0), name="ck_condicion_tasa_no_negativa"),
            models.CheckConstraint(condition=models.Q(mora_valor__gte=0), name="ck_condicion_mora_no_negativa"),
            models.CheckConstraint(condition=models.Q(tasa_periodo__in=PERIODOS_VALIDOS), name="ck_condicion_tasa_periodo"),
            models.CheckConstraint(condition=models.Q(mora_periodo__in=PERIODOS_VALIDOS), name="ck_condicion_mora_periodo"),
            # La capitalización solo existe en tasas nominales y no puede superar el periodo.
            models.CheckConstraint(
                condition=(models.Q(tasa_tipo="EFECTIVA", tasa_capitalizacion__isnull=True))
                | (
                    models.Q(tasa_tipo="NOMINAL", tasa_capitalizacion__in=PERIODOS_VALIDOS)
                    & models.Q(tasa_capitalizacion__lte=models.F("tasa_periodo"))
                ),
                name="ck_condicion_tasa_capitalizacion",
            ),
            models.CheckConstraint(
                condition=(models.Q(mora_tipo="EFECTIVA", mora_capitalizacion__isnull=True))
                | (
                    models.Q(mora_tipo="NOMINAL", mora_capitalizacion__in=PERIODOS_VALIDOS)
                    & models.Q(mora_capitalizacion__lte=models.F("mora_periodo"))
                ),
                name="ck_condicion_mora_capitalizacion",
            ),
            models.CheckConstraint(condition=models.Q(limite__gt=0), name="ck_condicion_limite_positivo"),
            models.CheckConstraint(condition=models.Q(plazo_max__gte=1, plazo_max__lte=60), name="ck_condicion_plazo_1_60"),
            # RN04: corte 1–27, pago 2–28 y pago posterior al corte (evita fechas inexistentes como 30 de febrero).
            models.CheckConstraint(condition=models.Q(dia_corte__gte=1, dia_corte__lte=27), name="ck_condicion_dia_corte"),
            models.CheckConstraint(condition=models.Q(dia_pago__gte=2, dia_pago__lte=28), name="ck_condicion_dia_pago"),
            models.CheckConstraint(condition=models.Q(dia_pago__gt=models.F("dia_corte")), name="ck_condicion_pago_despues_corte"),
            models.CheckConstraint(
                condition=models.Q(vigente_hasta__isnull=True) | models.Q(vigente_hasta__gte=models.F("vigente_desde")),
                name="ck_condicion_vigencia",
            ),
        ]

    def __str__(self):
        return f"{self.cuenta} · v{self.version}"

    def normalizar(self):
        """Aplica las convenciones del curso cuando falta un dato de la tasa (Anexo A):
        tasa nominal sin capitalización → diaria; tasa efectiva → sin capitalización."""
        if self.tasa_tipo == TipoTasa.NOMINAL and not self.tasa_capitalizacion:
            self.tasa_capitalizacion = PeriodoTasa.DIARIA
        if self.tasa_tipo == TipoTasa.EFECTIVA:
            self.tasa_capitalizacion = None
        if self.mora_tipo == TipoTasa.NOMINAL and not self.mora_capitalizacion:
            self.mora_capitalizacion = PeriodoTasa.DIARIA
        if self.mora_tipo == TipoTasa.EFECTIVA:
            self.mora_capitalizacion = None

    def clean(self):
        self.normalizar()
        errores = {}
        for prefijo, nombre in (("tasa", "compensatoria"), ("mora", "moratoria")):
            periodo = getattr(self, f"{prefijo}_periodo")
            cap = getattr(self, f"{prefijo}_capitalizacion")
            if cap and periodo and periodo % cap != 0:
                errores[f"{prefijo}_capitalizacion"] = (
                    f"La capitalización de la tasa {nombre} ({cap} días) debe dividir exactamente "
                    f"a su periodo ({periodo} días), para que m = p/c sea un número entero."
                )
        if self.dia_corte and self.dia_pago and self.dia_pago <= self.dia_corte:
            errores["dia_pago"] = (
                f"El día de pago ({self.dia_pago}) debe ser posterior al día de corte ({self.dia_corte}) (RN04)."
            )
        if errores:
            raise ValidationError(errores)

    def save(self, *args, **kwargs):
        if self._state.adding:
            self.normalizar()
        super().save(*args, **kwargs)
