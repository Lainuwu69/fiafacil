"""
Pruebas de la anulación de ventas y pagos (corrección trazable de errores; sección 5.3 del informe).

Reglas: una venta se anula solo si no tiene obligaciones pagadas; un pago se anula solo si es el
último vigente de la cuenta; siempre con motivo; nada se borra (RN09) y todo queda auditado.
"""

import uuid
from datetime import date
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.http import Http404
from django.test import TestCase
from django.urls import reverse

from core.constantes import TipoTasa
from core.fabricas_prueba import crear_articulo, crear_condicion, crear_cuenta, crear_tienda, crear_usuario, lima
from core.models import Auditoria
from creditos import servicios as s
from creditos.models import Anulacion, Compra, EstadoCuenta, Obligacion, Pago
from cuentas.models import Membresia

AHORA = lima(2026, 9, 25, 12)
CORTE_SEP = lima(2026, 9, 20, 20)
MOTIVO = "Se registró por error en otra cuenta"


class BaseAnulacion(TestCase):
    def setUp(self):
        self.usuario = crear_usuario()
        self.tienda = crear_tienda()
        Membresia.objects.create(usuario=self.usuario, tienda=self.tienda, rol="NEGOCIO")
        self.articulo = crear_articulo(self.tienda)
        self.c001 = crear_cuenta(self.tienda)
        crear_condicion(self.c001)

    def vender(self, monto, fecha, cuenta=None, modalidad="MENSUAL", n=None):
        return s.registrar_compra(self.usuario, self.tienda, (cuenta or self.c001).pk,
                                  [{"articulo_id": self.articulo.pk, "cantidad": str(monto)}], modalidad, n, fecha,
                                  uuid.uuid4(), ahora=AHORA)

    def pagar(self, obligaciones, fecha, importe, cuenta=None):
        return s.registrar_pago(self.usuario, self.tienda, (cuenta or self.c001).pk, [o.pk for o in obligaciones], fecha,
                                importe, uuid.uuid4(), ahora=lima(fecha.year, fecha.month, fecha.day, 18))


class AnularCompraTests(BaseAnulacion):
    def test_anular_venta_libera_el_credito_y_conserva_el_registro(self):
        compra = self.vender(120, lima(2026, 9, 5, 10))
        self.assertEqual(s.disponible(self.c001), Decimal("880.00"))
        anulacion = s.anular_compra(self.usuario, self.tienda, compra.pk, MOTIVO)
        compra.refresh_from_db()
        self.assertTrue(compra.anulada)
        self.assertEqual(list(compra.obligaciones.values_list("estado", flat=True)), ["ANULADA"])
        self.assertEqual(s.disponible(self.c001), Decimal("1000.00"))
        self.assertEqual((anulacion.tipo, anulacion.motivo), ("COMPRA", MOTIVO))
        self.assertTrue(Compra.objects.filter(pk=compra.pk).exists())  # nada se borra (RN09)
        self.assertTrue(Auditoria.objects.filter(evento="ANULACION").exists())

    def test_no_se_anula_una_venta_con_pagos(self):
        compra = self.vender(120, lima(2026, 9, 5, 10))
        self.pagar(list(compra.obligaciones.all()), date(2026, 9, 26), "121.52")
        with self.assertRaisesMessage(s.ErrorNegocio, "primero anula esos pagos"):
            s.anular_compra(self.usuario, self.tienda, compra.pk, MOTIVO)

    def test_motivo_obligatorio_y_una_sola_anulacion(self):
        compra = self.vender(120, lima(2026, 9, 5, 10))
        with self.assertRaisesMessage(s.ErrorNegocio, "mínimo 10 caracteres"):
            s.anular_compra(self.usuario, self.tienda, compra.pk, "error")
        s.anular_compra(self.usuario, self.tienda, compra.pk, MOTIVO)
        with self.assertRaisesMessage(s.ErrorNegocio, "ya está anulada"):
            s.anular_compra(self.usuario, self.tienda, compra.pk, MOTIVO)
        self.assertEqual(Anulacion.objects.count(), 1)

    def test_venta_anulada_no_entra_al_estado_ni_a_la_mora(self):
        k1 = self.vender(120, lima(2026, 9, 5, 10))
        self.vender(80, lima(2026, 9, 18, 10))
        s.anular_compra(self.usuario, self.tienda, k1.pk, MOTIVO)
        estado = s.generar_estado(self.c001, CORTE_SEP, ahora=lima(2026, 9, 21))
        self.assertEqual(estado.total, Decimal("80.38"))
        self.assertEqual(estado.detalles.count(), 1)
        o = Obligacion.objects.get(compra=k1)
        with self.assertRaisesMessage(s.ErrorNegocio, "venta anulada"):
            s.calcular_pago(self.c001, [o.pk], date(2026, 10, 1), ahora=lima(2026, 10, 1, 12))

    def test_anular_despues_de_generar_el_estado_lo_marca_sin_alterarlo(self):
        k1 = self.vender(120, lima(2026, 9, 5, 10))
        self.vender(80, lima(2026, 9, 18, 10))
        s.generar_estado(self.c001, CORTE_SEP, ahora=lima(2026, 9, 21))
        s.anular_compra(self.usuario, self.tienda, k1.pk, MOTIVO)
        r = s.resumen_ciclo(self.c001, CORTE_SEP, al_dia=date(2026, 9, 26))
        self.assertEqual(r["total"], Decimal("201.90"))  # el documento generado queda congelado
        self.assertEqual([ln["anulada"] for ln in r["lineas"]], [True, False])
        self.assertEqual(r["pendiente"], Decimal("80.38"))  # pero solo se cobra lo vigente

    def test_tienda_ajena_404_y_auditada(self):
        compra = self.vender(120, lima(2026, 9, 5, 10))
        otra = crear_tienda(nombre="Otra")
        with self.assertRaises(Http404):
            s.anular_compra(crear_usuario("x@otra.pe"), otra, compra.pk, MOTIVO)
        self.assertTrue(Auditoria.objects.filter(evento="ACCESO_DENEGADO", tienda=otra).exists())


class AnularPagoTests(BaseAnulacion):
    def setUp(self):
        super().setUp()
        self.c002 = crear_cuenta(self.tienda, documento="87654321")
        crear_condicion(self.c002, tasa_tipo=TipoTasa.NOMINAL, tasa_capitalizacion=30)
        self.compra = self.vender(600, lima(2026, 9, 15, 10), cuenta=self.c002, modalidad="CUOTAS", n=3)
        self.cuota1 = self.compra.obligaciones.get(numero=1)
        self.pago1 = self.pagar([self.cuota1], date(2026, 10, 26), "209.57", cuenta=self.c002)

    def test_anular_pago_devuelve_la_obligacion_a_pendiente_y_se_puede_volver_a_cobrar(self):
        self.assertEqual(s.disponible(self.c002), Decimal("593.11"))
        s.anular_pago(self.usuario, self.tienda, self.pago1.pk, "Se cobró con un importe equivocado")
        self.pago1.refresh_from_db()
        self.cuota1.refresh_from_db()
        self.assertTrue(self.pago1.anulado)
        self.assertEqual((self.cuota1.estado, self.cuota1.pagada_en), ("PENDIENTE", None))
        self.assertEqual(s.disponible(self.c002), Decimal("395.63"))
        # 1 día de atraso: 209.57 × [(1.03)^(1/360) − 1] = 0.0172 → 0.02; total 209.59
        nuevo = self.pagar([self.cuota1], date(2026, 10, 27), "209.59", cuenta=self.c002)
        self.assertEqual(nuevo.mora, Decimal("0.02"))
        self.assertEqual(Pago.objects.filter(cuenta=self.c002).count(), 2)

    def test_solo_se_anula_el_ultimo_pago(self):
        pago2 = self.pagar([self.compra.obligaciones.get(numero=2)], date(2026, 11, 26), "209.57", cuenta=self.c002)
        with self.assertRaisesMessage(s.ErrorNegocio, "Solo se puede anular el último pago"):
            s.anular_pago(self.usuario, self.tienda, self.pago1.pk, MOTIVO)
        s.anular_pago(self.usuario, self.tienda, pago2.pk, MOTIVO)
        s.anular_pago(self.usuario, self.tienda, self.pago1.pk, MOTIVO)  # ahora sí, en orden inverso
        self.assertEqual(Obligacion.objects.filter(compra=self.compra, estado="PENDIENTE").count(), 3)

    def test_la_base_impide_dos_aplicaciones_vigentes_para_una_obligacion(self):
        from creditos.models import PagoAplicacion

        otro = Pago.objects.create(tienda=self.tienda, numero=99, cuenta=self.c002, moneda="PEN",
                                   fecha_efectiva=date(2026, 10, 26), mora=Decimal("0"), interes=Decimal("12.09"),
                                   capital=Decimal("197.48"), total=Decimal("209.57"), clave_idempotencia=uuid.uuid4(),
                                   registrado_por=self.usuario)
        with self.assertRaises(IntegrityError), transaction.atomic():
            PagoAplicacion.objects.create(pago=otro, obligacion=self.cuota1, dias_mora=0, mora=Decimal("0"),
                                          interes=Decimal("12.09"), capital=Decimal("197.48"), total=Decimal("209.57"))

    def test_indicadores_no_cuentan_lo_anulado(self):
        s.anular_pago(self.usuario, self.tienda, self.pago1.pk, MOTIVO)
        s.anular_compra(self.usuario, self.tienda, self.compra.pk, MOTIVO)
        ind = s.indicadores_cartera(self.tienda, hoy=date(2026, 10, 30))["PEN"]
        self.assertEqual((ind["capital"], ind["cobrado_mes"], ind["ventas_90"]), (Decimal("0.00"), Decimal("0.00"), Decimal("0.00")))


class AnulacionPantallasTests(BaseAnulacion):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.usuario)

    def test_anular_venta_desde_el_detalle(self):
        compra = self.vender(120, lima(2026, 9, 5, 10))
        url = reverse("creditos:compra", args=[compra.pk])
        self.assertContains(self.client.get(url), "Anular la venta")
        r = self.client.post(reverse("creditos:anular_compra", args=[compra.pk]), {"motivo": MOTIVO})
        self.assertRedirects(r, url)
        detalle = self.client.get(url)
        self.assertContains(detalle, "ANULADA")
        self.assertContains(detalle, MOTIVO)

    def test_anular_pago_desde_el_comprobante(self):
        compra = self.vender(120, lima(2026, 9, 5, 10))
        pago = self.pagar(list(compra.obligaciones.all()), date(2026, 9, 26), "121.52")
        url = reverse("creditos:comprobante", args=[pago.pk])
        self.client.post(reverse("creditos:anular_pago", args=[pago.pk]), {"motivo": "corto"})
        pago.refresh_from_db()
        self.assertFalse(pago.anulado)  # motivo demasiado corto
        self.client.post(reverse("creditos:anular_pago", args=[pago.pk]), {"motivo": MOTIVO})
        self.assertContains(self.client.get(url), "ANULADO")

    def test_cliente_no_puede_anular(self):
        compra = self.vender(120, lima(2026, 9, 5, 10))
        cliente = crear_usuario("carmen@cliente.pe")
        self.c001.usuario = cliente
        self.c001.save()
        self.client.force_login(cliente)
        self.assertEqual(self.client.post(reverse("creditos:anular_compra", args=[compra.pk]), {"motivo": MOTIVO}).status_code, 403)
        compra.refresh_from_db()
        self.assertFalse(compra.anulada)
