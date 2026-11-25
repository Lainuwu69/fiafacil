"""
Pruebas de los servicios transaccionales (creditos/servicios.py), fase 4.

Criterio de aceptación (CLAUDE.md, fase 4): juegos A y B grabados en PostgreSQL
(estado 201.90, pago 201.98, disponible 950.00; Pg 604.37, disponible 395.63 y
luego 593.11), límite exacto, plazo excedido, fecha futura, cambio de tasa,
idempotencia y acceso a tienda ajena (404).
"""

import uuid
from datetime import date
from decimal import Decimal

from django.http import Http404
from django.test import TestCase

from core.constantes import Modalidad, TipoTasa
from core.fabricas_prueba import crear_articulo, crear_condicion, crear_cuenta, crear_tienda, crear_usuario, lima
from core.models import Auditoria, TopeTasa
from creditos import finanzas as fin
from creditos import servicios as s
from creditos.models import Compra, EstadoCuenta, Obligacion, Pago
from tiendas.models import Tienda

AHORA = lima(2026, 9, 25, 12)
CORTE_SEP = lima(2026, 9, 20, 20)
CORTE_OCT = lima(2026, 10, 20, 20)
M, C = Modalidad.MENSUAL, Modalidad.CUOTAS


def datos_condicion(**cambios):
    datos = {
        "tasa_tipo": TipoTasa.EFECTIVA, "tasa_valor": Decimal("0.24"), "tasa_periodo": 360, "tasa_capitalizacion": None,
        "mora_tipo": TipoTasa.EFECTIVA, "mora_valor": Decimal("0.03"), "mora_periodo": 360, "mora_capitalizacion": None,
        "limite": Decimal("1000.00"), "plazo_max": 3, "dia_corte": 20, "hora_corte": CORTE_SEP.timetz().replace(tzinfo=None),
        "dia_pago": 26,
    }
    datos.update(cambios)
    return datos


class BaseServicio(TestCase):
    def setUp(self):
        self.usuario = crear_usuario()
        self.tienda = crear_tienda()
        self.articulo = crear_articulo(self.tienda)  # "Consumo general" a S/ 1.00
        self.c001 = crear_cuenta(self.tienda)  # juego A
        crear_condicion(self.c001)
        self.c002 = crear_cuenta(self.tienda, documento="87654321", nombre="Pedro Huamán")  # juego B
        crear_condicion(self.c002, tasa_tipo=TipoTasa.NOMINAL, tasa_capitalizacion=30)

    def vender(self, cuenta, monto, fecha, modalidad=M, n=None, clave=None, ahora=AHORA, articulo=None):
        lineas = [{"articulo_id": (articulo or self.articulo).pk, "cantidad": str(monto)}]
        return s.registrar_compra(self.usuario, self.tienda, cuenta.pk, lineas, modalidad, n, fecha,
                                  clave or uuid.uuid4(), ahora=ahora)

    def pagar(self, cuenta, obligaciones, fecha, importe, clave=None, ahora=None):
        return s.registrar_pago(self.usuario, self.tienda, cuenta.pk, [o.pk for o in obligaciones], fecha, importe,
                                clave or uuid.uuid4(), ahora=ahora or lima(fecha.year, fecha.month, fecha.day, 18))


class JuegoAServicioTests(BaseServicio):
    def setUp(self):
        super().setUp()
        self.k1 = self.vender(self.c001, 120, lima(2026, 9, 5, 10))
        self.k2 = self.vender(self.c001, 80, lima(2026, 9, 18, 10))
        self.k3 = self.vender(self.c001, 50, lima(2026, 9, 21, 10))

    def test_compras_grabadas(self):
        self.assertEqual([self.k1.interes, self.k2.interes], [Decimal("1.52"), Decimal("0.38")])
        self.assertEqual(self.k3.fecha_pago, date(2026, 10, 26))
        self.assertEqual(self.k1.condicion.version, 1)
        self.assertEqual(self.k1.detalles.get().descripcion, "Consumo general")
        self.assertEqual(s.exposicion(self.c001), Decimal("250.00"))

    def test_estado_de_septiembre(self):
        estado = s.generar_estado(self.c001, CORTE_SEP, self.usuario, ahora=lima(2026, 9, 21))
        self.assertEqual((estado.capital, estado.interes, estado.total), (Decimal("200.00"), Decimal("1.90"), Decimal("201.90")))
        self.assertEqual(estado.fecha_pago, date(2026, 9, 26))
        self.assertEqual([d.capital for d in estado.detalles.order_by("orden")], [Decimal("120.00"), Decimal("80.00")])

    def test_pago_con_mora_201_98_y_prelacion(self):
        obligaciones = list(Obligacion.objects.filter(corte=CORTE_SEP, cuenta=self.c001))
        liq = s.calcular_pago(self.c001, [o.pk for o in obligaciones], date(2026, 10, 1), ahora=lima(2026, 10, 1, 12))
        self.assertEqual((liq.mora, liq.interes, liq.capital, liq.total),
                         (Decimal("0.08"), Decimal("1.90"), Decimal("200.00"), Decimal("201.98")))
        self.assertEqual([it.mora for it in liq.items], [Decimal("0.05"), Decimal("0.03")])  # reparto de la mora del total
        pago = self.pagar(self.c001, obligaciones, date(2026, 10, 1), "201.98")
        self.assertEqual((pago.mora, pago.interes, pago.capital, pago.total),
                         (Decimal("0.08"), Decimal("1.90"), Decimal("200.00"), Decimal("201.98")))
        self.assertEqual(pago.aplicaciones.count(), 2)
        self.assertFalse(Obligacion.objects.filter(corte=CORTE_SEP, estado="PENDIENTE").exists())
        self.assertEqual(s.exposicion(self.c001), Decimal("50.00"))
        self.assertEqual(s.disponible(self.c001), Decimal("950.00"))
        self.assertTrue(Auditoria.objects.filter(evento="PAGO", objeto_id=str(pago.pk)).exists())

    def test_pago_parcial_de_150_rechazado(self):
        obligaciones = list(Obligacion.objects.filter(corte=CORTE_SEP))
        with self.assertRaisesMessage(s.ErrorNegocio, "No se aceptan pagos parciales"):
            self.pagar(self.c001, obligaciones, date(2026, 10, 1), "150.00")
        self.assertEqual(Pago.objects.count(), 0)
        self.assertEqual(Obligacion.objects.filter(corte=CORTE_SEP, estado="PENDIENTE").count(), 2)
        self.assertTrue(Auditoria.objects.filter(evento="PAGO_RECHAZADO").exists())

    def test_pago_de_mas_rechazado(self):
        with self.assertRaises(s.ErrorNegocio):
            self.pagar(self.c001, list(Obligacion.objects.filter(corte=CORTE_SEP)), date(2026, 10, 1), "202.00")

    def test_mora_proyectada_y_pagada_como_item_separado(self):
        antes = s.resumen_ciclo(self.c001, CORTE_SEP, al_dia=date(2026, 10, 1))
        self.assertEqual((antes["total"], antes["mora_proyectada"], antes["dias_atraso"]), (Decimal("201.90"), Decimal("0.08"), 5))
        self.pagar(self.c001, list(Obligacion.objects.filter(corte=CORTE_SEP)), date(2026, 10, 1), "201.98")
        despues = s.resumen_ciclo(self.c001, CORTE_SEP, al_dia=date(2026, 10, 15))
        self.assertEqual((despues["mora_pagada"], despues["mora_proyectada"]), (Decimal("0.08"), Decimal("0.00")))

    def test_obligacion_ya_pagada(self):
        obligaciones = list(Obligacion.objects.filter(corte=CORTE_SEP))
        self.pagar(self.c001, obligaciones, date(2026, 9, 26), "201.90")
        with self.assertRaisesMessage(s.ErrorNegocio, "ya está pagada"):
            self.pagar(self.c001, obligaciones, date(2026, 9, 27), "201.90")

    def test_pago_puntual_sin_mora(self):
        pago = self.pagar(self.c001, list(Obligacion.objects.filter(corte=CORTE_SEP)), date(2026, 9, 26), "201.90")
        self.assertEqual(pago.mora, Decimal("0.00"))

    def test_estado_antes_del_corte_rechazado_y_generacion_idempotente(self):
        with self.assertRaises(s.ErrorNegocio):
            s.generar_estado(self.c001, CORTE_SEP, ahora=lima(2026, 9, 20, 19, 59))
        e1 = s.generar_estado(self.c001, CORTE_SEP, ahora=lima(2026, 9, 21))
        e2 = s.generar_estado(self.c001, CORTE_SEP, ahora=lima(2026, 9, 22))
        self.assertEqual(e1.pk, e2.pk)
        self.assertEqual(EstadoCuenta.objects.count(), 1)

    def test_no_se_agrega_compra_a_un_ciclo_cerrado(self):
        s.generar_estado(self.c001, CORTE_SEP, ahora=lima(2026, 9, 21))
        with self.assertRaisesMessage(s.ErrorNegocio, "ya fue generado"):
            self.vender(self.c001, 10, lima(2026, 9, 10, 9))

    def test_comando_diario_genera_los_cortes_cumplidos(self):
        generados = s.generar_estados_pendientes(ahora=lima(2026, 10, 21))
        self.assertEqual(sorted(e.total for e in generados), [Decimal("51.06"), Decimal("201.90")])
        self.assertEqual(s.generar_estados_pendientes(ahora=lima(2026, 10, 22)), [])


class JuegoBServicioTests(BaseServicio):
    def setUp(self):
        super().setUp()
        self.compra = self.vender(self.c002, 600, lima(2026, 9, 15, 10), modalidad=C, n=3)

    def test_compra_en_cuotas(self):
        self.assertEqual(self.compra.capital_con_gracia, Decimal("604.37"))
        self.assertEqual(self.compra.cuota, Decimal("209.57"))
        self.assertEqual(self.compra.total, Decimal("628.71"))
        self.assertEqual(self.compra.dias, 11)
        self.assertEqual(self.compra.tasa_periodo, Decimal("0.020000000000000"))
        self.assertEqual(self.compra.tcea.quantize(Decimal("1E-7")), Decimal("0.2682737"))
        cuotas = list(self.compra.obligaciones.order_by("numero"))
        self.assertEqual([o.vencimiento for o in cuotas], [date(2026, 10, 26), date(2026, 11, 26), date(2026, 12, 26)])
        self.assertEqual([o.saldo_final for o in cuotas], [Decimal("406.89"), Decimal("205.46"), Decimal("0.00")])
        self.assertEqual(cuotas[0].corte, CORTE_OCT)

    def test_disponibles_395_63_y_593_11(self):
        self.assertEqual(s.disponible(self.c002), Decimal("395.63"))
        cuota1 = self.compra.obligaciones.get(numero=1)
        pago = self.pagar(self.c002, [cuota1], date(2026, 10, 26), "209.57")
        self.assertEqual((pago.mora, pago.interes, pago.capital), (Decimal("0.00"), Decimal("12.09"), Decimal("197.48")))
        self.assertEqual(s.disponible(self.c002), Decimal("593.11"))

    def test_cuotas_se_pagan_en_orden(self):
        with self.assertRaisesMessage(s.ErrorNegocio, "Primero debe pagarse la cuota 1"):
            self.pagar(self.c002, [self.compra.obligaciones.get(numero=2)], date(2026, 10, 26), "209.57")

    def test_estado_de_octubre_incluye_la_cuota_1(self):
        estado = s.generar_estado(self.c002, CORTE_OCT, ahora=lima(2026, 10, 21))
        self.assertEqual(estado.total, Decimal("209.57"))
        self.assertIn("Cuota 1/3", estado.detalles.get().descripcion)

    def test_flujo_de_cobranzas_proyectado(self):
        flujo = s.flujo_cobranzas(self.tienda, hoy=date(2026, 10, 1), meses=3)["PEN"]
        por_mes = {f["etiqueta"]: f["total"] for f in flujo}
        self.assertEqual(por_mes["10/2026"], Decimal("209.57"))
        self.assertEqual(por_mes["11/2026"], Decimal("209.57"))
        self.assertEqual(por_mes["12/2026"], Decimal("209.57"))
        self.assertEqual(por_mes["Vencido (por cobrar)"], Decimal("0"))


class ReglasDeCompraTests(BaseServicio):
    def test_limite_exacto_100_y_100_01(self):
        cuenta = crear_cuenta(self.tienda, documento="11112222")
        crear_condicion(cuenta, limite=Decimal("100.00"))
        with self.assertRaisesMessage(s.ErrorNegocio, "Disponible: S/ 100.00; se necesita: S/ 100.01"):
            self.vender(cuenta, "100.01", lima(2026, 9, 10, 9))
        self.vender(cuenta, "100.00", lima(2026, 9, 10, 9))
        self.assertEqual(s.disponible(cuenta), Decimal("0.00"))
        self.assertTrue(Auditoria.objects.filter(evento="COMPRA_RECHAZADA").exists())

    def test_limite_en_cuotas_usa_capital_con_gracia(self):
        """RN06: en cuotas se compara Pg (604.37), no el capital (600)."""
        cuenta = crear_cuenta(self.tienda, documento="33334444")
        crear_condicion(cuenta, limite=Decimal("602.00"), tasa_tipo=TipoTasa.NOMINAL, tasa_capitalizacion=30)
        with self.assertRaisesMessage(s.ErrorNegocio, "excede el límite"):
            self.vender(cuenta, 600, lima(2026, 9, 15, 10), modalidad=C, n=3)

    def test_plazo_excedido(self):
        with self.assertRaisesMessage(s.ErrorNegocio, "entre 1 y el máximo pactado (3)"):
            self.vender(self.c002, 300, lima(2026, 9, 15, 10), modalidad=C, n=4)

    def test_fecha_futura(self):
        with self.assertRaisesMessage(s.ErrorNegocio, "no puede ser futura"):
            self.vender(self.c001, 10, lima(2026, 9, 25, 12, 1))

    def test_fecha_pasada_permitida_para_pasar_el_cuaderno(self):
        compra = self.vender(self.c001, 10, lima(2026, 9, 2, 8))
        self.assertLess(compra.fecha_compra, compra.registrada_en)

    def test_modalidad_no_permitida_por_el_articulo(self):
        solo_mes = crear_articulo(self.tienda, descripcion="Pan", permite_cuotas=False)
        with self.assertRaisesMessage(s.ErrorNegocio, "no se vende en cuotas"):
            self.vender(self.c002, 10, lima(2026, 9, 15, 10), modalidad=C, n=2, articulo=solo_mes)

    def test_articulo_de_otra_tienda(self):
        ajeno = crear_articulo(crear_tienda(nombre="Otra"))
        with self.assertRaisesMessage(s.ErrorNegocio, "no existe en el catálogo de esta tienda"):
            self.vender(self.c001, 10, lima(2026, 9, 10), articulo=ajeno)

    def test_cuenta_inactiva_y_tienda_pendiente(self):
        self.c001.activo = False
        self.c001.save()
        with self.assertRaisesMessage(s.ErrorNegocio, "dada de baja"):
            self.vender(self.c001, 10, lima(2026, 9, 10))
        self.tienda.estado = Tienda.Estado.PENDIENTE
        self.tienda.save()
        with self.assertRaisesMessage(s.ErrorNegocio, "no está activa"):
            self.vender(self.c002, 10, lima(2026, 9, 10))

    def test_idempotencia_de_compra_y_pago(self):
        clave = uuid.uuid4()
        a = self.vender(self.c001, 120, lima(2026, 9, 5, 10), clave=clave)
        b = self.vender(self.c001, 120, lima(2026, 9, 5, 10), clave=clave)
        self.assertEqual(a.pk, b.pk)
        self.assertEqual(Compra.objects.count(), 1)
        clave_pago = uuid.uuid4()
        p1 = self.pagar(self.c001, list(a.obligaciones.all()), date(2026, 9, 26), "121.52", clave=clave_pago)
        p2 = self.pagar(self.c001, list(a.obligaciones.all()), date(2026, 9, 26), "121.52", clave=clave_pago)
        self.assertEqual(p1.pk, p2.pk)
        self.assertEqual(Pago.objects.count(), 1)

    def test_tienda_ajena_responde_404_y_se_audita(self):
        intruso, otra = crear_usuario("intruso@otra.pe"), crear_tienda(nombre="Otra tienda")
        with self.assertRaises(Http404):
            s.registrar_compra(intruso, otra, self.c001.pk, [{"articulo_id": self.articulo.pk, "cantidad": "1"}],
                               M, None, lima(2026, 9, 10), uuid.uuid4(), ahora=AHORA)
        with self.assertRaises(Http404):
            s.registrar_pago(intruso, otra, self.c001.pk, [], date(2026, 9, 26), "1", uuid.uuid4(), ahora=AHORA)
        self.assertEqual(Auditoria.objects.filter(evento="ACCESO_DENEGADO", tienda=otra).count(), 2)
        self.assertEqual(Compra.objects.count(), 0)


class CondicionServicioTests(BaseServicio):
    def test_cambio_de_tasa_no_afecta_compras_previas(self):
        """RN10: la compra del 05/09 conserva la TEA 24 %; la del 18/09 usa la nueva TEA 30 %."""
        k1 = self.vender(self.c001, 120, lima(2026, 9, 5, 10))
        v2 = s.guardar_condicion(self.c001, self.usuario, datos_condicion(tasa_valor=Decimal("0.30")),
                                 vigente_desde=lima(2026, 9, 10), ahora=AHORA)
        k2 = self.vender(self.c001, 80, lima(2026, 9, 18, 10))
        k1.refresh_from_db()
        self.assertEqual((k1.condicion.version, k1.interes), (1, Decimal("1.52")))
        esperado = fin.compra_mensual(Decimal("80"), fin.Tasa("EFECTIVA", Decimal("0.30")), k2.fecha_compra, date(2026, 9, 26)).interes
        self.assertEqual((k2.condicion, k2.interes), (v2, esperado))
        self.assertNotEqual(k2.interes, Decimal("0.38"))
        self.assertTrue(Auditoria.objects.filter(evento="CONDICION").exists())

    def test_nueva_version_no_puede_regir_antes_de_la_ultima_compra(self):
        self.vender(self.c001, 120, lima(2026, 9, 5, 10))
        with self.assertRaisesMessage(s.ErrorNegocio, "antes de la última compra"):
            s.guardar_condicion(self.c001, self.usuario, datos_condicion(), vigente_desde=lima(2026, 9, 4), ahora=AHORA)

    def test_tope_del_bcrp(self):
        TopeTasa.objects.create(moneda="PEN", tipo="COMPENSATORIA", tasa_efectiva_anual=Decimal("0.20"),
                                vigente_desde=date(2026, 1, 1), fuente_url="https://www.bcrp.gob.pe/")
        with self.assertRaisesMessage(s.ErrorNegocio, "supera el tope del BCRP"):
            s.guardar_condicion(self.c001, self.usuario, datos_condicion(), vigente_desde=lima(2026, 9, 10), ahora=AHORA)

    def test_simulacion_no_graba_nada(self):
        sim = s.calcular_compra(self.c002, [{"articulo_id": self.articulo.pk, "cantidad": "600"}], C, 3,
                                lima(2026, 9, 15, 10), ahora=AHORA)
        self.assertTrue(sim.valida)
        self.assertEqual((sim.nueva_exposicion, sim.disponible_despues), (Decimal("604.37"), Decimal("395.63")))
        self.assertEqual(len(sim.alternativas), 5)  # contado, fin de mes y 1, 2, 3 cuotas
        self.assertEqual(Compra.objects.count(), 0)
