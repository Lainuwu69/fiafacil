"""
Funciones que crean datos de prueba con valores por defecto (solo para pruebas).

Los valores por defecto reproducen las condiciones comunes de los juegos A y B
del informe (sección 3.4): tienda T001, PEN, límite 1,000, 3 cuotas máximo,
corte el día 20 a las 20:00, pago el 26, moratoria TEA 3 %.
"""

import uuid
from datetime import date, datetime, time
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone

from clientes.models import CondicionCredito, CuentaCliente
from core.constantes import Modalidad, TipoTasa
from creditos.models import Compra, Obligacion
from tiendas.models import Articulo, Tienda

CLAVE_PRUEBA = "Fiafacil-2026"


def lima(anio, mes, dia, hora=0, minuto=0, segundo=0):
    """Fecha y hora con zona America/Lima."""
    return timezone.make_aware(datetime(anio, mes, dia, hora, minuto, segundo))


def crear_usuario(email="rosa@bodega.pe", **extra):
    extra.setdefault("nombres", email.split("@")[0].capitalize())
    return get_user_model().objects.create_user(email, CLAVE_PRUEBA, **extra)


def crear_tienda(**extra):
    datos = {"nombre": "Bodega Doña Rosa", "giro": "Bodega", "direccion": "Av. Siempre Viva 123", "estado": Tienda.Estado.ACTIVA}
    datos.update(extra)
    return Tienda.objects.create(**datos)


def crear_articulo(tienda, **extra):
    datos = {
        "tienda": tienda,
        "descripcion": "Consumo general",
        "unidad": Articulo.Unidad.UNIDAD,
        "imagen": "articulos/prueba.png",
        "precio_contado": Decimal("1.00"),
        "precio_credito": Decimal("1.00"),
        "permite_mensual": True,
        "permite_cuotas": True,
    }
    datos.update(extra)
    return Articulo.objects.create(**datos)


def crear_cuenta(tienda, **extra):
    datos = {"tienda": tienda, "documento": "45678912", "nombre": "Carmen Quispe Rojas"}
    datos.update(extra)
    return CuentaCliente.objects.create(**datos)


def crear_condicion(cuenta, **extra):
    """Condición del juego A (TEA 24 %). Para el juego B usar tasa_tipo=NOMINAL, tasa_capitalizacion=30."""
    datos = {
        "cuenta": cuenta,
        "version": 1,
        "tasa_tipo": TipoTasa.EFECTIVA,
        "tasa_valor": Decimal("0.24"),
        "tasa_periodo": 360,
        "mora_tipo": TipoTasa.EFECTIVA,
        "mora_valor": Decimal("0.03"),
        "mora_periodo": 360,
        "limite": Decimal("1000.00"),
        "plazo_max": 3,
        "dia_corte": 20,
        "hora_corte": time(20, 0),
        "dia_pago": 26,
        "vigente_desde": lima(2026, 9, 1),
    }
    datos.update(extra)
    return CondicionCredito.objects.create(**datos)


def crear_compra_mensual(cuenta, condicion, usuario, numero=1, capital="120.00", interes="1.52", **extra):
    """Compra mensual mínima con su obligación (valores de la primera compra del juego A)."""
    capital, interes = Decimal(capital), Decimal(interes)
    datos = {
        "tienda": cuenta.tienda,
        "numero": numero,
        "cuenta": cuenta,
        "condicion": condicion,
        "moneda": cuenta.moneda,
        "fecha_compra": lima(2026, 9, 5, 10),
        "modalidad": Modalidad.MENSUAL,
        "capital": capital,
        "corte": lima(2026, 9, 20, 20),
        "fecha_pago": date(2026, 9, 26),
        "dias": 21,
        "tasa_periodo": Decimal("0.012627000000000"),
        "interes": interes,
        "total": capital + interes,
        "clave_idempotencia": uuid.uuid4(),
        "registrada_por": usuario,
    }
    datos.update(extra)
    compra = Compra.objects.create(**datos)
    obligacion = Obligacion.objects.create(
        tienda=cuenta.tienda,
        cuenta=cuenta,
        compra=compra,
        numero=1,
        tipo=Obligacion.Tipo.MENSUAL,
        corte=compra.corte,
        vencimiento=compra.fecha_pago,
        capital=capital,
        interes=interes,
        total=capital + interes,
    )
    return compra, obligacion
