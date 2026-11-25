"""
Listas de valores compartidas por varias apps (monedas, tipos de tasa, periodos).

Se definen una sola vez para que la base de datos, los formularios y los
cálculos usen exactamente los mismos códigos.
"""

from django.db import models


class Moneda(models.TextChoices):
    """RN02: una cuenta tiene una sola moneda; no hay tipo de cambio."""

    PEN = "PEN", "Soles (S/)"
    USD = "USD", "Dólares (US$)"


SIMBOLO_MONEDA = {Moneda.PEN: "S/", Moneda.USD: "US$"}


class TipoTasa(models.TextChoices):
    """Una tasa pactada puede ser nominal (necesita capitalización) o efectiva."""

    NOMINAL = "NOMINAL", "Nominal"
    EFECTIVA = "EFECTIVA", "Efectiva"


class PeriodoTasa(models.IntegerChoices):
    """Duración en días del periodo de una tasa o de su capitalización (año de 360 días)."""

    DIARIA = 1, "Diaria (1 día)"
    QUINCENAL = 15, "Quincenal (15 días)"
    MENSUAL = 30, "Mensual (30 días)"
    BIMESTRAL = 60, "Bimestral (60 días)"
    TRIMESTRAL = 90, "Trimestral (90 días)"
    CUATRIMESTRAL = 120, "Cuatrimestral (120 días)"
    SEMESTRAL = 180, "Semestral (180 días)"
    ANUAL = 360, "Anual (360 días)"


PERIODOS_VALIDOS = [p.value for p in PeriodoTasa]


class Modalidad(models.TextChoices):
    """RN05: pago único en la fecha de pago del ciclo, o cuotas por el método francés."""

    MENSUAL = "MENSUAL", "Pago a fin de mes (fecha de pago)"
    CUOTAS = "CUOTAS", "En cuotas mensuales (método francés)"
