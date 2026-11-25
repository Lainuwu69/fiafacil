from django.apps import AppConfig


class ClientesConfig(AppConfig):
    """Cuentas de los clientes de cada tienda y sus condiciones de crédito."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "clientes"
    verbose_name = "Clientes y condiciones"
