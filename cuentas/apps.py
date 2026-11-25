from django.apps import AppConfig


class CuentasConfig(AppConfig):
    """Usuarios, membresías, registro e inicio de sesión."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "cuentas"
    verbose_name = "Cuentas de usuario"

    def ready(self):
        from cuentas import signals  # noqa: F401  (registra la auditoría de login y logout)
