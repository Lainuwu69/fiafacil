"""
Modelos transversales (capítulo 5 del informe):

- Auditoria: bitácora inmutable de todo lo que ocurre en el sistema
  (requisito del punto 9: "registrar todas las operaciones en una base de datos").
- TopeTasa: tasas máximas publicadas por el BCRP (Circular 0008-2021-BCRP),
  con su fuente oficial y vigencia. Se usan para advertir si una tasa pactada
  las supera. Los valores se cargan desde la fuente oficial; nunca se inventan.
"""

from django.conf import settings
from django.db import models
from django.db.models import F, Q

from core.campos import tasa
from core.constantes import Moneda
from core.modelos_base import RegistroInmutable


class Auditoria(RegistroInmutable):
    """Evento registrado: quién, cuándo, en qué tienda, qué hizo y sobre qué objeto. Nunca guarda contraseñas."""

    class Evento(models.TextChoices):
        LOGIN = "LOGIN", "Inicio de sesión"
        LOGIN_FALLIDO = "LOGIN_FALLIDO", "Inicio de sesión fallido"
        LOGOUT = "LOGOUT", "Cierre de sesión"
        REGISTRO = "REGISTRO", "Registro de usuario y tienda"
        ALTA = "ALTA", "Alta"
        MODIFICACION = "MODIFICACION", "Modificación"
        BAJA = "BAJA", "Baja"
        ACTIVACION = "ACTIVACION", "Activación de tienda"
        CONDICION = "CONDICION", "Nueva versión de condiciones"
        COMPRA = "COMPRA", "Compra al crédito"
        COMPRA_RECHAZADA = "COMPRA_RECHAZADA", "Compra rechazada"
        ESTADO = "ESTADO", "Estado de cuenta generado"
        PAGO = "PAGO", "Pago registrado"
        PAGO_RECHAZADO = "PAGO_RECHAZADO", "Pago rechazado"
        ANULACION = "ANULACION", "Anulación"
        CAMBIO_CLAVE = "CAMBIO_CLAVE", "Cambio de contraseña"
        ACCESO_DENEGADO = "ACCESO_DENEGADO", "Acceso denegado"

    id = models.BigAutoField(primary_key=True)
    instante = models.DateTimeField("instante", auto_now_add=True, db_index=True, help_text="Momento del evento.")
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        help_text="Quién realizó la acción; vacío si no hay sesión (por ejemplo, un login fallido).",
    )
    tienda = models.ForeignKey(
        "tiendas.Tienda", on_delete=models.PROTECT, null=True, blank=True, related_name="+", help_text="Tienda afectada, si aplica."
    )
    evento = models.CharField("evento", max_length=20, choices=Evento.choices, help_text="Tipo de acción registrada.")
    objeto_tipo = models.CharField("tipo de objeto", max_length=60, blank=True, help_text="Entidad afectada. Ej.: Compra, Pago.")
    objeto_id = models.CharField("id del objeto", max_length=64, blank=True, help_text="Identificador del registro afectado.")
    descripcion = models.CharField("descripción", max_length=300, help_text="Resumen legible del evento.")
    datos = models.JSONField("datos", default=dict, blank=True, help_text="Detalle adicional (importes, motivo del rechazo, etc.).")
    ip = models.GenericIPAddressField("IP", null=True, blank=True, help_text="Dirección IP desde la que se hizo la solicitud.")

    class Meta:
        db_table = "auditoria"
        verbose_name = "registro de auditoría"
        verbose_name_plural = "auditoría"
        ordering = ["-instante"]
        indexes = [models.Index(fields=["tienda", "-instante"], name="ix_auditoria_tienda_instante")]

    def __str__(self):
        return f"{self.instante:%d/%m/%Y %H:%M} · {self.get_evento_display()} · {self.descripcion}"

    @classmethod
    def registrar(cls, evento, descripcion, *, usuario=None, tienda=None, objeto=None, datos=None, request=None):
        """Crea un registro de auditoría. Se llama desde servicios y vistas."""
        if usuario is not None and not getattr(usuario, "is_authenticated", True):
            usuario = None
        ip = None
        if request is not None:
            ip = (request.META.get("HTTP_X_FORWARDED_FOR") or request.META.get("REMOTE_ADDR") or "").split(",")[0].strip() or None
        return cls.objects.create(
            evento=evento,
            descripcion=descripcion[:300],
            usuario=usuario,
            tienda=tienda,
            objeto_tipo=objeto.__class__.__name__ if objeto is not None else "",
            objeto_id=str(objeto.pk) if objeto is not None else "",
            datos=datos or {},
            ip=ip,
        )


class TopeTasa(models.Model):
    """Tasa máxima vigente (BCRP) por moneda y tipo. Catálogo normativo, distinto de la tasa pactada."""

    class Tipo(models.TextChoices):
        COMPENSATORIA = "COMPENSATORIA", "Compensatoria"
        MORATORIA = "MORATORIA", "Moratoria"

    id = models.BigAutoField(primary_key=True)
    moneda = models.CharField("moneda", max_length=3, choices=Moneda.choices, help_text="Moneda a la que aplica el tope.")
    tipo = models.CharField("tipo", max_length=13, choices=Tipo.choices, help_text="Tope de tasa compensatoria o moratoria.")
    tasa_efectiva_anual = tasa(
        "tasa efectiva anual máxima", "Tope expresado como TEA decimal (por ejemplo 0.8 = 80 %), copiado de la fuente oficial."
    )
    vigente_desde = models.DateField("vigente desde", help_text="Primer día de vigencia según la publicación del BCRP.")
    vigente_hasta = models.DateField("vigente hasta", null=True, blank=True, help_text="Último día de vigencia; vacío si sigue vigente.")
    fuente_url = models.URLField("URL de la fuente oficial", max_length=500, help_text="Enlace a la publicación oficial del BCRP.")
    observacion = models.CharField("observación", max_length=300, blank=True, help_text="Opcional. Nota sobre la publicación.")

    class Meta:
        db_table = "tope_tasa"
        verbose_name = "tope de tasa (BCRP)"
        verbose_name_plural = "topes de tasa (BCRP)"
        ordering = ["moneda", "tipo", "-vigente_desde"]
        constraints = [
            models.CheckConstraint(condition=Q(tasa_efectiva_anual__gt=0), name="ck_tope_positivo"),
            models.CheckConstraint(
                condition=Q(vigente_hasta__isnull=True) | Q(vigente_hasta__gte=F("vigente_desde")), name="ck_tope_vigencia"
            ),
            models.CheckConstraint(condition=Q(moneda__in=["PEN", "USD"]), name="ck_tope_moneda"),
        ]

    def __str__(self):
        return f"Tope {self.get_tipo_display()} {self.moneda} desde {self.vigente_desde:%d/%m/%Y}"
