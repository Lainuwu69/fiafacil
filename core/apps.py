from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Piezas transversales: auditoría, topes de tasa, panel, ayuda y portal."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
    verbose_name = "Núcleo y auditoría"
