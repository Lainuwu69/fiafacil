"""
Pruebas del modelo matemático puro (creditos/finanzas.py), fase 3.

Criterio de aceptación: reproducir EXACTAMENTE los juegos A y B y las pruebas de
frontera del informe del Hito 1 (sección 3.4). No usan base de datos
(SimpleTestCase), porque finanzas.py no depende de ella.
"""

from datetime import date, datetime, time
from decimal import Decimal

from django.test import SimpleTestCase

from creditos import finanzas as f
from creditos.finanzas import ZONA_LIMA, ErrorFinanciero, Tasa

DEC15 = Decimal("1E-15")
DEC7 = Decimal("1E-7")


def lima(anio, mes, dia, hora=0, minuto=0, segundo=0):
    return datetime(anio, mes, dia, hora, minuto, segundo, tzinfo=ZONA_LIMA)


def q(valor, exp):
    return valor.quantize(exp)


# Condiciones comunes a ambos juegos: corte día 20 a las 20:00, pago el 26, moratoria TEA 3 %.
CORTE, HORA, PAGO = 20, time(20, 0), 26
TEA_24 = Tasa("EFECTIVA", Decimal("0.24"), 360)
TNA_24_MENSUAL = Tasa("NOMINAL", Decimal("0.24"), 360, 30)
MORA_TEA_3 = Tasa("EFECTIVA", Decimal("0.03"), 360)


class RedondeoYFormatoTests(SimpleTestCase):
    def test_r2_half_up(self):
        """RN12: HALF_UP. Con float, 2.675 daría 2.67; con Decimal da 2.68."""
        self.assertEqual(f.r2("2.675"), Decimal("2.68"))
        self.assertEqual(f.r2("0.125"), Decimal("0.13"))
        self.assertEqual(f.r2("0.0829"), Decimal("0.08"))

    def test_no_acepta_float(self):
        with self.assertRaises(TypeError):
            f.r2(0.1)

    def test_tasa_con_al_menos_7_decimales(self):
        self.assertEqual(f.formato_tasa(Decimal("0.268241794562545")), "26.8241795 %")


class DiasYCicloTests(SimpleTestCase):
    def test_dias_exactos_excluye_inicio_incluye_final(self):
        self.assertEqual(f.dias_exactos(date(2026, 9, 26), date(2026, 10, 1)), 5)
        self.assertEqual(f.dias_exactos(date(2026, 10, 26), date(2026, 11, 1)), 6)
        self.assertEqual(f.dias_exactos(date(2026, 9, 26), date(2026, 9, 26)), 0)

    def test_dias_exactos_rechaza_intervalo_invertido(self):
        with self.assertRaises(ErrorFinanciero):
            f.dias_exactos(date(2026, 10, 1), date(2026, 9, 26))

    def test_frontera_del_corte_rn03(self):
        """19:59:59 entra al corte del 20/09; 20:00:00 y 20:00:01 pasan al de octubre."""
        casos = [
            (lima(2026, 9, 20, 19, 59, 59), date(2026, 9, 26)),
            (lima(2026, 9, 20, 20, 0, 0), date(2026, 10, 26)),
            (lima(2026, 9, 20, 20, 0, 1), date(2026, 10, 26)),
        ]
        for momento, pago_esperado in casos:
            with self.subTest(momento=momento.strftime("%H:%M:%S")):
                self.assertEqual(f.ciclo_de_compra(momento, CORTE, HORA, PAGO).fecha_pago, pago_esperado)

    def test_corte_se_evalua_en_hora_de_lima(self):
        """01:00 UTC del 21/09 son las 20:00 del 20/09 en Lima: pasa al ciclo siguiente."""
        from datetime import timezone as tz

        utc = datetime(2026, 9, 21, 0, 59, 59, tzinfo=tz.utc)  # 19:59:59 en Lima
        self.assertEqual(f.ciclo_de_compra(utc, CORTE, HORA, PAGO).fecha_pago, date(2026, 9, 26))
        utc = datetime(2026, 9, 21, 1, 0, 0, tzinfo=tz.utc)  # 20:00:00 en Lima
        self.assertEqual(f.ciclo_de_compra(utc, CORTE, HORA, PAGO).fecha_pago, date(2026, 10, 26))

    def test_cambio_de_anio(self):
        ciclo = f.ciclo_de_compra(lima(2026, 12, 21, 9), CORTE, HORA, PAGO)
        self.assertEqual(ciclo.corte, lima(2027, 1, 20, 20))
        self.assertEqual(ciclo.fecha_pago, date(2027, 1, 26))

    def test_calendario_invalido(self):
        with self.assertRaises(ErrorFinanciero):
            f.ciclo_de_compra(lima(2026, 9, 1), 20, HORA, 20)


class TasasTests(SimpleTestCase):
    def test_tem_desde_tea_juego_a(self):
        self.assertEqual(q(TEA_24.tem(), DEC15), Decimal("0.018087582483511"))

    def test_tem_y_tea_desde_tna_mensual_juego_b(self):
        self.assertEqual(q(TNA_24_MENSUAL.tem(), DEC15), Decimal("0.020000000000000"))
        self.assertEqual(q(TNA_24_MENSUAL.tea(), DEC15), Decimal("0.268241794562545"))

    def test_nominal_sin_capitalizacion_se_asume_diaria(self):
        t = Tasa("NOMINAL", Decimal("0.24"), 360, None)
        self.assertEqual(t.capitalizacion, 1)
        # TEA = (1 + 0.24/360)^360 − 1
        esperado = (Decimal(1) + Decimal("0.24") / 360) ** 360 - 1
        self.assertEqual(q(t.tea(), DEC15), q(esperado, DEC15))

    def test_periodo_omitido_se_asume_anual(self):
        self.assertEqual(Tasa("EFECTIVA", Decimal("0.24"), None).periodo, 360)

    def test_tea_no_se_divide_entre_12(self):
        self.assertNotEqual(q(TEA_24.tem(), DEC7), q(Decimal("0.24") / 12, DEC7))

    def test_capitalizacion_que_no_divide_el_periodo(self):
        with self.assertRaises(ErrorFinanciero):
            Tasa("NOMINAL", Decimal("0.24"), 120, 90)


class JuegoATests(SimpleTestCase):
    """Juego A: TEA 24 %, pago a fin de mes, mora TEA 3 % (informe 3.4.1)."""

    def test_compras_e_intereses(self):
        c1 = f.compra_mensual(Decimal("120"), TEA_24, lima(2026, 9, 5, 10), date(2026, 9, 26))
        c2 = f.compra_mensual(Decimal("80"), TEA_24, lima(2026, 9, 18, 10), date(2026, 9, 26))
        self.assertEqual((c1.dias, c1.interes), (21, Decimal("1.52")))
        self.assertEqual((c2.dias, c2.interes), (8, Decimal("0.38")))
        estado = c1.total + c2.total
        self.assertEqual(c1.capital + c2.capital, Decimal("200.00"))
        self.assertEqual(c1.interes + c2.interes, Decimal("1.90"))
        self.assertEqual(estado, Decimal("201.90"))

    def test_tercera_compra_pasa_a_octubre(self):
        ciclo = f.ciclo_de_compra(lima(2026, 9, 21, 10), CORTE, HORA, PAGO)
        self.assertEqual(ciclo.fecha_pago, date(2026, 10, 26))
        c3 = f.compra_mensual(Decimal("50"), TEA_24, lima(2026, 9, 21, 10), ciclo.fecha_pago)
        self.assertEqual(c3.dias, 35)

    def test_pago_con_5_dias_de_atraso(self):
        m = f.calcular_mora(Decimal("201.90"), MORA_TEA_3, date(2026, 9, 26), date(2026, 10, 1))
        self.assertEqual((m.dias, m.mora), (5, Decimal("0.08")))
        self.assertEqual(Decimal("201.90") + m.mora, Decimal("201.98"))

    def test_disponible_despues_del_pago(self):
        """Tras cancelar septiembre queda la compra de 50.00: disponible 950.00."""
        self.assertEqual(f.disponible(Decimal("1000"), Decimal("50.00")), Decimal("950.00"))


class JuegoBTests(SimpleTestCase):
    """Juego B: TNA 24 % capitalización mensual, 600 en 3 cuotas con gracia (informe 3.4.2)."""

    def setUp(self):
        compra = lima(2026, 9, 15, 10)
        self.ciclo = f.ciclo_de_compra(compra, CORTE, HORA, PAGO)
        self.r = f.compra_en_cuotas(Decimal("600"), TNA_24_MENSUAL, compra, self.ciclo.fecha_pago, 3)

    def test_gracia_y_cuota(self):
        self.assertEqual(self.ciclo.fecha_pago, date(2026, 9, 26))
        self.assertEqual(self.r.dias_gracia, 11)
        self.assertEqual(self.r.capital_con_gracia, Decimal("604.37"))
        self.assertEqual(self.r.interes_gracia, Decimal("4.37"))
        self.assertEqual(self.r.cuota, Decimal("209.57"))

    def test_cronograma(self):
        esperado = [
            (1, date(2026, 10, 26), "604.37", "12.09", "209.57", "197.48", "406.89"),
            (2, date(2026, 11, 26), "406.89", "8.14", "209.57", "201.43", "205.46"),
            (3, date(2026, 12, 26), "205.46", "4.11", "209.57", "205.46", "0.00"),
        ]
        for fila, (k, venc, si, i, c, a, sf) in zip(self.r.filas, esperado):
            with self.subTest(cuota=k):
                self.assertEqual(
                    (fila.numero, fila.vencimiento, fila.saldo_inicial, fila.interes, fila.cuota, fila.amortizacion, fila.saldo_final),
                    (k, venc, Decimal(si), Decimal(i), Decimal(c), Decimal(a), Decimal(sf)),
                )

    def test_totales(self):
        self.assertEqual(self.r.interes_cuotas, Decimal("24.34"))
        self.assertEqual(self.r.total_pagado, Decimal("628.71"))
        self.assertEqual(self.r.interes_total, Decimal("28.71"))
        self.assertEqual(sum(fl.amortizacion for fl in self.r.filas), Decimal("604.37"))

    def test_disponibles(self):
        self.assertEqual(f.disponible(Decimal("1000"), self.r.capital_con_gracia), Decimal("395.63"))
        self.assertEqual(f.disponible(Decimal("1000"), self.r.filas[0].saldo_final), Decimal("593.11"))

    def test_tcea(self):
        """Ajuste A: TCEA ≈ 26.83 %, apenas sobre la TEA de 26.82 % por el redondeo de cuotas."""
        valor = f.tcea(self.r.capital, f.flujos_de_cuotas(self.r))
        self.assertEqual(q(valor, DEC7), Decimal("0.2682737"))
        self.assertGreater(valor, TNA_24_MENSUAL.tea())


class FronteraTests(SimpleTestCase):
    def test_limite_exacto(self):
        """Disponible 100: se acepta 100.00 y se rechaza 100.01."""
        self.assertTrue(f.cabe_en_limite(Decimal("1000"), Decimal("900"), Decimal("100.00")))
        self.assertFalse(f.cabe_en_limite(Decimal("1000"), Decimal("900"), Decimal("100.01")))

    def test_tasa_cero(self):
        filas = f.cronograma_frances(Decimal("600"), Decimal("0"), 3, date(2026, 9, 26))
        self.assertEqual([fl.cuota for fl in filas], [Decimal("200.00")] * 3)

    def test_ajuste_de_la_ultima_cuota(self):
        filas = f.cronograma_frances(Decimal("100"), Decimal("0.02"), 3, date(2026, 9, 26))
        self.assertEqual([fl.cuota for fl in filas], [Decimal("34.68"), Decimal("34.68"), Decimal("34.67")])
        self.assertEqual([fl.interes for fl in filas], [Decimal("2.00"), Decimal("1.35"), Decimal("0.68")])
        self.assertEqual(filas[-1].saldo_final, Decimal("0.00"))

    def test_mora_entre_meses_6_dias(self):
        m = f.calcular_mora(Decimal("201.90"), MORA_TEA_3, date(2026, 10, 26), date(2026, 11, 1))
        self.assertEqual((m.dias, m.mora), (6, Decimal("0.10")))
        self.assertEqual(Decimal("201.90") + m.mora, Decimal("202.00"))

    def test_pago_puntual_o_adelantado_sin_mora(self):
        for pago in (date(2026, 9, 26), date(2026, 9, 25)):
            with self.subTest(pago=pago):
                self.assertEqual(f.calcular_mora(Decimal("201.90"), MORA_TEA_3, date(2026, 9, 26), pago).mora, Decimal("0.00"))

    def test_monto_muy_pequeno_para_las_cuotas(self):
        with self.assertRaises(ErrorFinanciero):
            f.cronograma_frances(Decimal("0.02"), Decimal("0.02"), 3, date(2026, 9, 26))


class TceaYAlternativasTests(SimpleTestCase):
    def test_sin_redondeo_la_tcea_es_la_tea(self):
        """Si se paga 124 a los 360 días por 100 recibidos, la TCEA es exactamente 24 %."""
        self.assertEqual(q(f.tcea(Decimal("100"), [(360, Decimal("124"))]), Decimal("1E-20")), Decimal("0.24").quantize(Decimal("1E-20")))

    def test_comparacion_de_alternativas(self):
        compra = lima(2026, 9, 15, 10)
        ciclo = f.ciclo_de_compra(compra, CORTE, HORA, PAGO)
        alts = f.comparar_alternativas(Decimal("600"), Decimal("570"), TNA_24_MENSUAL, compra, ciclo, 3)
        claves = [a.clave for a in alts]
        self.assertEqual(claves, ["CONTADO", "MENSUAL", "CUOTAS_1", "CUOTAS_2", "CUOTAS_3"])
        tres = alts[-1]
        self.assertEqual(tres.total, Decimal("628.71"))
        self.assertEqual(tres.costo_financiero, Decimal("58.71"))  # 628.71 − 570 de contado
        # Sobre el precio contado, el sobreprecio de lista eleva la TCEA por encima de la del juego B.
        self.assertGreater(tres.tcea, Decimal("0.2682737"))

    def test_respeta_modalidades_del_articulo(self):
        compra = lima(2026, 9, 15, 10)
        ciclo = f.ciclo_de_compra(compra, CORTE, HORA, PAGO)
        alts = f.comparar_alternativas(Decimal("50"), Decimal("50"), TEA_24, compra, ciclo, 3, permite_cuotas=False)
        self.assertEqual([a.clave for a in alts], ["CONTADO", "MENSUAL"])
