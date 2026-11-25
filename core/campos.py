"""
Tipos de campo estándar de FíaFácil.

- Importes: NUMERIC(18,2), como define el informe (sección 2.5 y capítulo 5).
- Tasas: NUMERIC(20,15), guardadas como decimal (24 % = 0.24), RN12.

Nunca se usa FloatField: un float no representa exactamente 0.10 y produce
errores de centavos. Decimal sí es exacto.
"""

from django.db import models


def importe(verbose_name, help_text, **opciones):
    """Campo monetario de 2 decimales (hasta 9,999,999,999,999,999.99)."""
    return models.DecimalField(
        verbose_name, max_digits=18, decimal_places=2, help_text=help_text, **opciones
    )


def tasa(verbose_name, help_text, **opciones):
    """Campo de tasa decimal con 15 decimales (0.240000000000000 = 24 %)."""
    return models.DecimalField(
        verbose_name, max_digits=20, decimal_places=15, help_text=help_text, **opciones
    )


def cantidad(verbose_name, help_text, **opciones):
    """Cantidad vendida con hasta 3 decimales (1.250 kg), NUMERIC(12,3)."""
    return models.DecimalField(
        verbose_name, max_digits=12, decimal_places=3, help_text=help_text, **opciones
    )
