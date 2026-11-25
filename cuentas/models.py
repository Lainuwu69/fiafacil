"""
Modelos de la app cuentas (capítulo 5 del informe).

- Usuario: persona que inicia sesión con su correo; id UUID.
- Membresia: vincula a un usuario con una tienda y un rol (NEGOCIO o CLIENTE).
  Así una misma persona puede administrar una tienda y ser cliente de otra.
"""

import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone

from core.modelos_base import SinBorradoFisico


class UsuarioManager(BaseUserManager):
    """Crea usuarios identificados por su correo (no hay 'username')."""

    use_in_migrations = True

    def _crear(self, email, password, **extra):
        if not email:
            raise ValueError("El correo es obligatorio.")
        email = self.normalize_email(email).lower()
        usuario = self.model(email=email, **extra)
        usuario.set_password(password)  # guarda el hash, nunca la clave en texto
        usuario.save(using=self._db)
        return usuario

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._crear(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        if extra.get("is_staff") is not True or extra.get("is_superuser") is not True:
            raise ValueError("El superusuario debe tener is_staff e is_superuser en True.")
        return self._crear(email, password, **extra)

    def get_by_natural_key(self, username):
        # El login no distingue mayúsculas: Rosa@Bodega.pe = rosa@bodega.pe
        return self.get(email__iexact=username)


class Usuario(AbstractBaseUser, PermissionsMixin):
    """Persona que entra al sistema: administrador de plataforma, negocio o cliente."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(
        "correo",
        max_length=254,
        unique=True,
        help_text="Correo con el que la persona inicia sesión. Debe ser único en la plataforma.",
    )
    nombres = models.CharField(
        "nombres", max_length=100, help_text="Nombres de la persona, tal como figuran en su documento."
    )
    apellidos = models.CharField(
        "apellidos", max_length=100, blank=True, help_text="Apellidos de la persona (opcional)."
    )
    is_active = models.BooleanField(
        "activo",
        default=True,
        help_text="Si se desmarca, la persona ya no puede iniciar sesión (baja lógica, RN09).",
    )
    is_staff = models.BooleanField(
        "administrador de plataforma",
        default=False,
        help_text="Marca a quien administra la plataforma: da de alta y baja tiendas.",
    )
    fecha_alta = models.DateTimeField(
        "fecha de alta", default=timezone.now, editable=False, help_text="Momento en que se creó el usuario."
    )

    objects = UsuarioManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["nombres"]

    class Meta:
        db_table = "usuario"
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"
        ordering = ["email"]
        constraints = [
            # Garantiza en la base que no haya dos correos iguales con distinta capitalización.
            models.UniqueConstraint(Lower("email"), name="uq_usuario_email_minusculas"),
        ]

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        self.email = (self.email or "").strip().lower()
        super().save(*args, **kwargs)

    def get_full_name(self):
        return f"{self.nombres} {self.apellidos}".strip()

    def get_short_name(self):
        return self.nombres


class Membresia(SinBorradoFisico):
    """Permiso de un usuario sobre una tienda (RN01: separación por tienda)."""

    class Rol(models.TextChoices):
        NEGOCIO = "NEGOCIO", "Administrador del negocio"
        CLIENTE = "CLIENTE", "Cliente"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="membresias",
        help_text="Persona que recibe el permiso.",
    )
    tienda = models.ForeignKey(
        "tiendas.Tienda",
        on_delete=models.PROTECT,
        related_name="membresias",
        help_text="Tienda sobre la que se otorga el permiso.",
    )
    rol = models.CharField(
        "rol",
        max_length=10,
        choices=Rol.choices,
        help_text="NEGOCIO administra la tienda; CLIENTE solo consulta sus propias cuentas.",
    )
    activo = models.BooleanField(
        "activa", default=True, help_text="Si se desmarca, el permiso queda revocado (baja lógica)."
    )
    fecha_alta = models.DateTimeField(
        "fecha de alta", default=timezone.now, editable=False, help_text="Momento en que se otorgó el permiso."
    )

    class Meta:
        db_table = "membresia"
        verbose_name = "membresía"
        verbose_name_plural = "membresías"
        constraints = [
            models.UniqueConstraint(fields=["usuario", "tienda", "rol"], name="uq_membresia_usuario_tienda_rol"),
            models.CheckConstraint(condition=models.Q(rol__in=["NEGOCIO", "CLIENTE"]), name="ck_membresia_rol"),
        ]

    def __str__(self):
        return f"{self.usuario} · {self.get_rol_display()} · {self.tienda}"
