"""
Modelos de la app tiendas (capítulo 5 del informe).

- Tienda: establecimiento de la plataforma multitienda.
- Articulo: producto o servicio del catálogo de una tienda (RN11).
"""

import uuid

from django.db import models
from django.db.models.functions import Cast, Substr
from django.utils import timezone

from core.campos import importe
from core.modelos_base import SinBorradoFisico, siguiente_numero


class Tienda(SinBorradoFisico):
    """Establecimiento que vende al crédito. Lo activa el administrador de plataforma."""

    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente de activación"
        ACTIVA = "ACTIVA", "Activa"
        INACTIVA = "INACTIVA", "Dada de baja"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    codigo = models.CharField(
        "código",
        max_length=10,
        unique=True,
        editable=False,
        help_text="Código correlativo asignado por el sistema, por ejemplo T001.",
    )
    nombre = models.CharField(
        "nombre comercial", max_length=120, help_text="Nombre con el que los vecinos conocen el negocio. Ej.: Bodega Doña Rosa."
    )
    giro = models.CharField(
        "giro", max_length=60, help_text="Actividad del negocio. Ej.: bodega, panadería, pollería, peluquería, spa."
    )
    ruc = models.CharField(
        "RUC",
        max_length=11,
        null=True,
        blank=True,
        help_text="Opcional. Si el negocio tiene RUC, escribe sus 11 dígitos sin espacios. Ej.: 10456789012.",
    )
    direccion = models.CharField(
        "dirección", max_length=200, help_text="Dirección del local. Ej.: Av. Los Álamos 123, San Juan de Lurigancho."
    )
    telefono = models.CharField(
        "teléfono", max_length=20, blank=True, help_text="Opcional. Celular o teléfono de contacto. Ej.: 987654321."
    )
    estado = models.CharField(
        "estado",
        max_length=10,
        choices=Estado.choices,
        default=Estado.PENDIENTE,
        help_text="PENDIENTE al registrarse; ACTIVA cuando la plataforma la habilita; INACTIVA si se da de baja (RN09).",
    )
    fecha_alta = models.DateTimeField(
        "fecha de registro", default=timezone.now, editable=False, help_text="Momento en que se registró la tienda."
    )
    fecha_activacion = models.DateTimeField(
        "fecha de activación", null=True, blank=True, help_text="Momento en que la plataforma activó la tienda."
    )
    fecha_baja = models.DateTimeField(
        "fecha de baja", null=True, blank=True, help_text="Momento en que se dio de baja la tienda; se conserva su historial."
    )

    class Meta:
        db_table = "tienda"
        verbose_name = "tienda"
        verbose_name_plural = "tiendas"
        ordering = ["codigo"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(estado__in=["PENDIENTE", "ACTIVA", "INACTIVA"]), name="ck_tienda_estado"
            ),
            models.CheckConstraint(
                condition=models.Q(ruc__isnull=True) | models.Q(ruc__regex=r"^[0-9]{11}$"), name="ck_tienda_ruc_11_digitos"
            ),
        ]

    def __str__(self):
        return f"{self.codigo} {self.nombre}"

    @property
    def esta_activa(self):
        return self.estado == self.Estado.ACTIVA

    def save(self, *args, **kwargs):
        if not self.codigo:
            n = siguiente_numero(
                Tienda.objects.filter(codigo__regex=r"^T[0-9]+$").annotate(
                    n=Cast(Substr("codigo", 2), models.IntegerField())
                ),
                "n",
            )
            self.codigo = f"T{n:03d}"
        if self.ruc == "":
            self.ruc = None
        super().save(*args, **kwargs)


class Articulo(SinBorradoFisico):
    """Producto o servicio que la tienda vende al crédito (RN11). No lleva stock."""

    class Unidad(models.TextChoices):
        UNIDAD = "UNIDAD", "Unidad"
        KG = "KG", "Kilogramo"
        GRAMO = "GRAMO", "Gramo"
        LITRO = "LITRO", "Litro"
        PAQUETE = "PAQUETE", "Paquete"
        DOCENA = "DOCENA", "Docena"
        SERVICIO = "SERVICIO", "Servicio"
        SESION = "SESION", "Sesión"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tienda = models.ForeignKey(
        Tienda, on_delete=models.PROTECT, related_name="articulos", help_text="Tienda dueña del artículo (RN01)."
    )
    descripcion = models.CharField(
        "descripción", max_length=200, help_text="Nombre claro del producto o servicio. Ej.: Arroz extra 5 kg, Corte de cabello."
    )
    proveedor = models.CharField(
        "proveedor", max_length=120, blank=True, help_text="Opcional. Quién te provee el producto. Déjalo vacío si es un servicio."
    )
    marca = models.CharField("marca", max_length=120, blank=True, help_text="Opcional. Ej.: Costeño, Gloria.")
    unidad = models.CharField(
        "unidad de medida",
        max_length=20,
        choices=Unidad.choices,
        default=Unidad.UNIDAD,
        help_text="Cómo se vende: por unidad, kilo, litro, servicio, etc.",
    )
    imagen = models.ImageField(
        "imagen",
        upload_to="articulos/%Y/%m/",
        max_length=500,
        help_text="Foto del producto o servicio (JPG, PNG o WEBP, máximo 2 MB). Es obligatoria.",
    )
    precio_contado = importe(
        "precio contado", "Precio si el cliente paga en el momento. Usa punto decimal. Ej.: 18.50."
    )
    precio_credito = importe(
        "precio de lista (crédito)",
        "Precio unitario que se financia cuando se vende al crédito; los intereses se calculan aparte. Ej.: 19.90.",
    )
    permite_mensual = models.BooleanField(
        "se vende a fin de mes", default=True, help_text="Marca si se puede pagar en un solo pago en la fecha de pago del ciclo."
    )
    permite_cuotas = models.BooleanField(
        "se vende en cuotas", default=False, help_text="Marca si se puede pagar en cuotas mensuales (método francés)."
    )
    activo = models.BooleanField(
        "activo", default=True, help_text="Desmárcalo para dar de baja el artículo sin borrar las ventas pasadas (RN09)."
    )
    fecha_alta = models.DateTimeField(
        "fecha de alta", default=timezone.now, editable=False, help_text="Momento en que se registró el artículo."
    )

    class Meta:
        db_table = "articulo"
        verbose_name = "artículo"
        verbose_name_plural = "artículos"
        ordering = ["descripcion"]
        constraints = [
            models.CheckConstraint(condition=models.Q(precio_contado__gt=0), name="ck_articulo_precio_contado_positivo"),
            models.CheckConstraint(condition=models.Q(precio_credito__gt=0), name="ck_articulo_precio_credito_positivo"),
            models.CheckConstraint(
                condition=models.Q(permite_mensual=True) | models.Q(permite_cuotas=True),
                name="ck_articulo_al_menos_una_modalidad",
            ),
            models.CheckConstraint(condition=~models.Q(imagen=""), name="ck_articulo_imagen_obligatoria"),
        ]

    def __str__(self):
        return self.descripcion
