from django.apps import AppConfig


class CreditosConfig(AppConfig):
    """Modelo financiero: compras, obligaciones, estados de cuenta y pagos."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "creditos"
    verbose_name = "Créditos y pagos"
