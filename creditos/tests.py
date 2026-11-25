"""
Pruebas de créditos.

Fase 2: restricciones de los modelos financieros en PostgreSQL (UNIQUE, CHECK,
inmutabilidad). Las fases 3 y 4 agregan aquí las pruebas de los juegos A y B,
frontera y reglas de negocio.
"""

import uuid
from datetime import date
from decimal import Decimal

from django.db import IntegrityError, connection, transaction
from django.test import TestCase

from core.fabricas_prueba import (
    crear_compra_mensual,
    crear_condicion,
    crear_cuenta,
    crear_tienda,
    crear_usuario,
    lima,
)
from core.models import Auditoria
from core.modelos_base import OperacionNoPermitida
from creditos.models import EstadoCuenta, EstadoDetalle, Obligacion, Pago, PagoAplicacion


class BaseFinanciera(TestCase):
    def setUp(self):
        self.usuario = crear_usuario()
        self.tienda = crear_tienda()
        self.cuenta = crear_cuenta(self.tienda)
        self.condicion = crear_condicion(self.cuenta)


class CompraRestriccionesTests(BaseFinanciera):
    def test_compra_mensual_valida(self):
        compra, obligacion = crear_compra_mensual(self.cuenta, self.condicion, self.usuario)
        self.assertEqual(compra.total, Decimal("121.52"))
        self.assertEqual(obligacion.total, Decimal("121.52"))

    def test_idempotencia_unica_por_tienda(self):
        clave = uuid.uuid4()
        crear_compra_mensual(self.cuenta, self.condicion, self.usuario, numero=1, clave_idempotencia=clave)
        with self.assertRaises(IntegrityError), transaction.atomic():
            crear_compra_mensual(self.cuenta, self.condicion, self.usuario, numero=2, clave_idempotencia=clave)

    def test_mensual_no_lleva_cuotas(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            crear_compra_mensual(self.cuenta, self.condicion, self.usuario, n_cuotas=3)

    def test_cuotas_exige_n_pg_y_cuota(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            crear_compra_mensual(self.cuenta, self.condicion, self.usuario, modalidad="CUOTAS")

    def test_corte_debe_ser_posterior_a_la_compra(self):
        """RN03: una compra a la hora exacta del corte no puede quedar en ese corte."""
        with self.assertRaises(IntegrityError), transaction.atomic():
            crear_compra_mensual(self.cuenta, self.condicion, self.usuario, fecha_compra=lima(2026, 9, 20, 20))

    def test_compra_no_se_modifica_ni_se_borra(self):
        compra, _ = crear_compra_mensual(self.cuenta, self.condicion, self.usuario)
        compra.capital = Decimal("999.00")
        with self.assertRaises(OperacionNoPermitida):
            compra.save()
        with self.assertRaises(OperacionNoPermitida):
            compra.delete()


class ObligacionRestriccionesTests(BaseFinanciera):
    def test_total_debe_ser_capital_mas_interes(self):
        compra, _ = crear_compra_mensual(self.cuenta, self.condicion, self.usuario)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Obligacion.objects.create(
                tienda=self.tienda, cuenta=self.cuenta, compra=compra, numero=2, tipo="MENSUAL",
                corte=compra.corte, vencimiento=compra.fecha_pago,
                capital=Decimal("10.00"), interes=Decimal("1.00"), total=Decimal("12.00"),
            )

    def test_pagada_exige_fecha_de_pago(self):
        _, obligacion = crear_compra_mensual(self.cuenta, self.condicion, self.usuario)
        obligacion.estado = Obligacion.Estado.PAGADA
        with self.assertRaises(IntegrityError), transaction.atomic():
            obligacion.save(update_fields=["estado"])

    def test_solo_estado_y_fecha_de_pago_son_actualizables(self):
        _, obligacion = crear_compra_mensual(self.cuenta, self.condicion, self.usuario)
        obligacion.estado, obligacion.pagada_en = Obligacion.Estado.PAGADA, date(2026, 10, 1)
        obligacion.save(update_fields=["estado", "pagada_en"])
        obligacion.capital = Decimal("1.00")
        with self.assertRaises(OperacionNoPermitida):
            obligacion.save(update_fields=["capital"])


class PagoRestriccionesTests(BaseFinanciera):
    def _pago(self, numero=1, **extra):
        datos = dict(
            tienda=self.tienda, numero=numero, cuenta=self.cuenta, moneda="PEN", fecha_efectiva=date(2026, 10, 1),
            mora=Decimal("0.08"), interes=Decimal("1.90"), capital=Decimal("200.00"), total=Decimal("201.98"),
            clave_idempotencia=uuid.uuid4(), registrado_por=self.usuario,
        )
        datos.update(extra)
        return Pago.objects.create(**datos)

    def test_total_debe_ser_mora_mas_interes_mas_capital(self):
        """Juego A: 0.08 + 1.90 + 200.00 = 201.98; un total distinto se rechaza en la base."""
        self.assertEqual(self._pago().total, Decimal("201.98"))
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._pago(numero=2, total=Decimal("150.00"))

    def test_obligacion_no_se_cobra_dos_veces(self):
        _, obligacion = crear_compra_mensual(self.cuenta, self.condicion, self.usuario)
        p1, p2 = self._pago(numero=1), self._pago(numero=2)
        comp = dict(obligacion=obligacion, dias_mora=0, mora=Decimal("0"), interes=Decimal("1.52"),
                    capital=Decimal("120.00"), total=Decimal("121.52"))
        PagoAplicacion.objects.create(pago=p1, **comp)
        with self.assertRaises(IntegrityError), transaction.atomic():
            PagoAplicacion.objects.create(pago=p2, **comp)

    def test_idempotencia_del_pago(self):
        clave = uuid.uuid4()
        self._pago(numero=1, clave_idempotencia=clave)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._pago(numero=2, clave_idempotencia=clave)


class EstadoCuentaRestriccionesTests(BaseFinanciera):
    def test_un_estado_por_cuenta_y_corte(self):
        datos = dict(tienda=self.tienda, cuenta=self.cuenta, corte=lima(2026, 9, 20, 20), fecha_pago=date(2026, 9, 26),
                     capital=Decimal("200.00"), interes=Decimal("1.90"), total=Decimal("201.90"))
        estado = EstadoCuenta.objects.create(**datos)
        with self.assertRaises(IntegrityError), transaction.atomic():
            EstadoCuenta.objects.create(**datos)
        _, obligacion = crear_compra_mensual(self.cuenta, self.condicion, self.usuario)
        linea = dict(estado=estado, obligacion=obligacion, orden=1, fecha_compra=lima(2026, 9, 5, 10),
                     descripcion="Compra 1", capital=Decimal("120.00"), interes=Decimal("1.52"), total=Decimal("121.52"))
        EstadoDetalle.objects.create(**linea)
        with self.assertRaises(IntegrityError), transaction.atomic():
            EstadoDetalle.objects.create(**linea)


class AuditoriaTests(BaseFinanciera):
    def test_registrar_y_no_modificar(self):
        a = Auditoria.registrar(Auditoria.Evento.LOGIN, "Inicio de sesión de prueba", usuario=self.usuario, tienda=self.tienda)
        self.assertEqual(a.usuario, self.usuario)
        a.descripcion = "alterado"
        with self.assertRaises(OperacionNoPermitida):
            a.save()
        with self.assertRaises(OperacionNoPermitida):
            a.delete()


class EsquemaTests(TestCase):
    def test_existen_las_15_tablas_del_capitulo_5(self):
        esperadas = {
            "usuario", "membresia", "tienda", "articulo", "cuenta_cliente", "condicion_credito", "compra",
            "detalle_compra", "obligacion", "estado_cuenta", "estado_detalle", "pago", "pago_aplicacion",
            "auditoria", "tope_tasa",
        }
        tablas = set(connection.introspection.table_names())
        self.assertEqual(esperadas - tablas, set())

    def test_importes_numeric_18_2_y_tasas_numeric_20_15(self):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT table_name, column_name, numeric_precision, numeric_scale FROM information_schema.columns "
                "WHERE (table_name, column_name) IN (('compra','capital'), ('pago','total'), ('condicion_credito','tasa_valor'))"
            )
            tipos = {(t, c): (p, s) for t, c, p, s in cursor.fetchall()}
        self.assertEqual(tipos[("compra", "capital")], (18, 2))
        self.assertEqual(tipos[("pago", "total")], (18, 2))
        self.assertEqual(tipos[("condicion_credito", "tasa_valor")], (20, 15))
