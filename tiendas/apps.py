from django.apps import AppConfig


class TiendasConfig(AppConfig):
    """Tiendas de la plataforma y su catálogo de artículos."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "tiendas"
    verbose_name = "Tiendas y catálogo"
