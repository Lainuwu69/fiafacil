"""Pruebas de la fase 2: restricciones de CuentaCliente y CondicionCredito (RN02, RN04, RN10)."""

from datetime import time
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from clientes.models import CondicionCredito
from core.constantes import TipoTasa
from core.fabricas_prueba import crear_condicion, crear_cuenta, crear_tienda, lima
from core.modelos_base import OperacionNoPermitida


class CuentaClienteTests(TestCase):
    def setUp(self):
        self.tienda = crear_tienda()

    def test_codigo_correlativo_por_tienda(self):
        c1 = crear_cuenta(self.tienda)
        c2 = crear_cuenta(self.tienda, documento="11111111", nombre="Luis Pérez")
        otra = crear_cuenta(crear_tienda(nombre="Otra"), documento="22222222")
        self.assertEqual((c1.codigo, c2.codigo, otra.codigo), ("C001", "C002", "C001"))

    def test_mismo_documento_y_moneda_no_se_repite_en_la_tienda(self):
        crear_cuenta(self.tienda)
        with self.assertRaises(IntegrityError), transaction.atomic():
            crear_cuenta(self.tienda)

    def test_mismo_cliente_puede_tener_cuenta_en_otra_moneda(self):
        """RN02: una cuenta, una moneda. Para dólares se abre otra cuenta."""
        crear_cuenta(self.tienda, moneda="PEN")
        usd = crear_cuenta(self.tienda, moneda="USD")
        self.assertEqual(usd.moneda, "USD")

    def test_moneda_invalida_rechazada(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            crear_cuenta(self.tienda, moneda="EUR")


class CondicionCreditoTests(TestCase):
    def setUp(self):
        self.cuenta = crear_cuenta(crear_tienda())

    def test_tasas_se_guardan_como_decimal(self):
        c = crear_condicion(self.cuenta)
        c.refresh_from_db()
        self.assertEqual(c.tasa_valor, Decimal("0.240000000000000"))

    def test_nominal_sin_capitalizacion_se_asume_diaria(self):
        """Convención del curso: tasa nominal sin capitalización indicada → diaria."""
        c = crear_condicion(self.cuenta, tasa_tipo=TipoTasa.NOMINAL, tasa_capitalizacion=None)
        self.assertEqual(c.tasa_capitalizacion, 1)

    def test_efectiva_no_lleva_capitalizacion(self):
        c = crear_condicion(self.cuenta, tasa_capitalizacion=30)
        self.assertIsNone(c.tasa_capitalizacion)

    def test_capitalizacion_mayor_que_el_periodo_rechazada_por_bd(self):
        # bulk_create no pasa por save()/normalizar(): así se prueba el CHECK de la base directamente.
        mala = CondicionCredito(cuenta=self.cuenta, version=1, tasa_tipo="NOMINAL", tasa_valor=Decimal("0.24"),
                                tasa_periodo=30, tasa_capitalizacion=360, mora_tipo="EFECTIVA",
                                mora_valor=Decimal("0.03"), mora_periodo=360, limite=Decimal("1000"), plazo_max=3,
                                dia_corte=20, hora_corte=time(20), dia_pago=26, vigente_desde=lima(2026, 9, 1))
        with self.assertRaises(IntegrityError), transaction.atomic():
            CondicionCredito.objects.bulk_create([mala])

    def test_capitalizacion_debe_dividir_el_periodo(self):
        c = CondicionCredito(cuenta=self.cuenta, version=1, tasa_tipo="NOMINAL", tasa_valor=Decimal("0.24"),
                             tasa_periodo=120, tasa_capitalizacion=90, mora_tipo="EFECTIVA",
                             mora_valor=Decimal("0.03"), mora_periodo=360, limite=Decimal("1000"), plazo_max=3,
                             dia_corte=20, hora_corte=time(20), dia_pago=26)
        with self.assertRaises(ValidationError) as ctx:
            c.full_clean()
        self.assertIn("tasa_capitalizacion", ctx.exception.message_dict)

    def test_calendario_rn04(self):
        casos = [
            {"dia_corte": 28},  # corte fuera de 1–27
            {"dia_pago": 29},  # pago fuera de 2–28
            {"dia_corte": 20, "dia_pago": 20},  # pago no posterior al corte
            {"dia_corte": 20, "dia_pago": 15},
        ]
        for extra in casos:
            with self.subTest(**extra), self.assertRaises(IntegrityError), transaction.atomic():
                crear_condicion(self.cuenta, **extra)

    def test_limite_y_plazo(self):
        for extra in ({"limite": Decimal("0")}, {"plazo_max": 0}, {"plazo_max": 61}, {"tasa_valor": Decimal("-0.01")}):
            with self.subTest(**{k: str(v) for k, v in extra.items()}), self.assertRaises(IntegrityError), transaction.atomic():
                crear_condicion(self.cuenta, **extra)

    def test_solo_una_version_vigente(self):
        crear_condicion(self.cuenta)
        with self.assertRaises(IntegrityError), transaction.atomic():
            crear_condicion(self.cuenta, version=2)

    def test_version_inmutable_solo_se_cierra(self):
        """RN10: una versión no se edita; se cierra y se crea otra."""
        v1 = crear_condicion(self.cuenta)
        v1.tasa_valor = Decimal("0.30")
        with self.assertRaises(OperacionNoPermitida):
            v1.save()
        v1.refresh_from_db()
        v1.vigente_hasta = lima(2026, 10, 1)
        v1.save(update_fields=["vigente_hasta"])
        v2 = crear_condicion(self.cuenta, version=2, tasa_valor=Decimal("0.30"), vigente_desde=lima(2026, 10, 1))
        self.assertEqual(self.cuenta.condicion_vigente(), v2)
        with self.assertRaises(OperacionNoPermitida):
            v1.delete()
