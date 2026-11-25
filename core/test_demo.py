"""Pruebas del comando cargar_demo (fase 9): reproduce los juegos A y B con los servicios reales."""

from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings

from clientes.models import CuentaCliente
from creditos import servicios as s
from creditos.models import Compra, EstadoCuenta, Pago
from tiendas.models import Tienda

Usuario = get_user_model()


@override_settings(MEDIA_ROOT="media_pruebas")
class CargarDemoTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree("media_pruebas", ignore_errors=True)
        super().tearDownClass()

    def ejecutar(self, *args):
        salida = StringIO()
        call_command("cargar_demo", *args, stdout=salida)
        return salida.getvalue()

    def test_sin_operaciones_deja_todo_listo_para_la_demo(self):
        self.ejecutar()
        for email in ("admin@fiafacil.pe", "rosa@bodega.pe", "carmen@cliente.pe"):
            self.assertTrue(Usuario.objects.get(email=email).check_password("Fiafacil-2026"))
        self.assertTrue(Usuario.objects.get(email="admin@fiafacil.pe").is_staff)
        tienda = Tienda.objects.get(codigo="T001")
        self.assertEqual((tienda.nombre, tienda.estado), ("Bodega Doña Rosa", "ACTIVA"))
        c001 = CuentaCliente.objects.get(tienda=tienda, codigo="C001")
        self.assertEqual(c001.usuario.email, "carmen@cliente.pe")
        self.assertEqual(c001.condicion_vigente().tasa_tipo, "EFECTIVA")
        self.assertEqual(CuentaCliente.objects.get(codigo="C002").condicion_vigente().tasa_capitalizacion, 30)
        self.assertEqual(tienda.articulos.get(descripcion="Consumo general").precio_credito, Decimal("1.00"))
        self.assertFalse(Compra.objects.exists())

    def test_con_operaciones_reproduce_los_juegos(self):
        texto = self.ejecutar("--con-operaciones")
        c001 = CuentaCliente.objects.get(codigo="C001")
        c002 = CuentaCliente.objects.get(codigo="C002")
        self.assertEqual(EstadoCuenta.objects.filter(cuenta=c001).order_by("corte").first().total, Decimal("201.90"))
        self.assertEqual(Pago.objects.get(cuenta=c001).total, Decimal("201.98"))
        self.assertEqual(s.disponible(c001), Decimal("950.00"))
        compra_b = Compra.objects.get(cuenta=c002)
        self.assertEqual((compra_b.capital_con_gracia, compra_b.cuota), (Decimal("604.37"), Decimal("209.57")))
        self.assertEqual(s.disponible(c002), Decimal("593.11"))
        self.assertIn("disponible C001 950.00", texto)

    def test_es_idempotente(self):
        self.ejecutar("--con-operaciones")
        self.ejecutar("--con-operaciones")
        self.assertEqual(Tienda.objects.count(), 1)
        self.assertEqual(CuentaCliente.objects.count(), 2)
        self.assertEqual(Compra.objects.count(), 4)
        self.assertEqual(Pago.objects.count(), 2)

    def test_topes_bcrp_oficiales_y_su_efecto(self):
        """Nota BCRP del 01/10/2026: 114.68 % (PEN) y 103.14 % (USD) del 01/11/2026 al 30/04/2027."""
        from datetime import datetime, time

        from django.utils import timezone

        from core.models import TopeTasa

        call_command("cargar_topes_bcrp", stdout=StringIO())
        call_command("cargar_topes_bcrp", stdout=StringIO())  # idempotente
        self.assertEqual(TopeTasa.objects.count(), 4)  # mayo–octubre 2026 y noviembre 2026 – abril 2027
        self.assertEqual(TopeTasa.objects.get(moneda="PEN", vigente_desde__month=11).tasa_efectiva_anual, Decimal("1.146800000000000"))
        self.assertEqual(TopeTasa.objects.get(moneda="USD", vigente_desde__month=5).tasa_efectiva_anual, Decimal("0.998400000000000"))
        self.ejecutar()
        cuenta = CuentaCliente.objects.get(codigo="C001")
        rosa = Usuario.objects.get(email="rosa@bodega.pe")
        datos = {"tasa_tipo": "EFECTIVA", "tasa_valor": Decimal("1.20"), "tasa_periodo": 360, "tasa_capitalizacion": None,
                 "mora_tipo": "EFECTIVA", "mora_valor": Decimal("0.03"), "mora_periodo": 360, "mora_capitalizacion": None,
                 "limite": Decimal("1000"), "plazo_max": 3, "dia_corte": 20, "hora_corte": time(20), "dia_pago": 26}
        ahora = timezone.make_aware(datetime(2026, 11, 25, 12))
        with self.assertRaisesMessage(s.ErrorNegocio, "supera el tope del BCRP"):  # TEA 120 % > 114.68 %
            s.guardar_condicion(cuenta, rosa, datos, vigente_desde=ahora, ahora=ahora)
        datos["tasa_valor"] = Decimal("0.24")  # juego A: muy por debajo del tope
        self.assertEqual(s.guardar_condicion(cuenta, rosa, datos, vigente_desde=ahora, ahora=ahora).version, 2)

    def test_reiniciar_exige_confirmacion(self):
        self.ejecutar("--con-operaciones")
        # Con anulaciones registradas (protegen ventas y pagos), el reinicio también debe funcionar.
        rosa = Usuario.objects.get(email="rosa@bodega.pe")
        pago = Pago.objects.get(cuenta__codigo="C001")
        s.anular_pago(rosa, pago.tienda, pago.pk, "Prueba de reinicio con anulaciones")
        with self.assertRaises(CommandError):
            self.ejecutar("--reiniciar")
        self.ejecutar("--reiniciar", "--si")
        self.assertFalse(Pago.objects.exists())
        self.assertEqual(Tienda.objects.get().codigo, "T001")
        self.assertEqual(Usuario.objects.count(), 3)
