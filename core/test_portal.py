"""
Pruebas del portal del cliente (fase 7): el cliente solo consulta y solo ve lo suyo.
"""

import uuid
from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from core.constantes import TipoTasa
from core.fabricas_prueba import crear_articulo, crear_condicion, crear_cuenta, crear_tienda, crear_usuario, lima
from core.models import Auditoria
from creditos import servicios as s
from creditos.models import Obligacion
from cuentas.models import Membresia


class PortalTests(TestCase):
    def setUp(self):
        self.negocio = crear_usuario("rosa@bodega.pe")
        self.tienda = crear_tienda()
        self.articulo = crear_articulo(self.tienda)
        self.carmen = crear_usuario("carmen@cliente.pe", nombres="Carmen")
        self.c001 = crear_cuenta(self.tienda, usuario=self.carmen)  # juego A
        crear_condicion(self.c001)
        Membresia.objects.create(usuario=self.carmen, tienda=self.tienda, rol="CLIENTE")
        self.c002 = crear_cuenta(self.tienda, documento="87654321", nombre="Pedro Huamán")  # otro cliente
        crear_condicion(self.c002, tasa_tipo=TipoTasa.NOMINAL, tasa_capitalizacion=30)
        ahora = lima(2026, 9, 25, 12)
        for cuenta, monto, fecha in ((self.c001, 120, lima(2026, 9, 5, 10)), (self.c001, 80, lima(2026, 9, 18, 10)),
                                     (self.c002, 600, lima(2026, 9, 15, 10))):
            s.registrar_compra(self.negocio, self.tienda, cuenta.pk, [{"articulo_id": self.articulo.pk, "cantidad": str(monto)}],
                               "MENSUAL", None, fecha, uuid.uuid4(), ahora=ahora)
        obligaciones = list(Obligacion.objects.filter(cuenta=self.c001))
        self.pago = s.registrar_pago(self.negocio, self.tienda, self.c001.pk, [o.pk for o in obligaciones], date(2026, 10, 1),
                                     "201.98", uuid.uuid4(), ahora=lima(2026, 10, 1, 12))
        self.client.force_login(self.carmen)

    def test_inicio_muestra_solo_sus_cuentas(self):
        r = self.client.get(reverse("core:portal"))
        self.assertEqual([t["cuenta"] for t in r.context["tarjetas"]], [self.c001])
        self.assertNotContains(r, "Pedro Huamán")
        self.assertEqual(r.context["tarjetas"][0]["disponible"], Decimal("1000.00"))

    def test_detalle_compra_estado_y_comprobante_propios(self):
        self.assertEqual(self.client.get(reverse("core:portal_cuenta", args=[self.c001.pk])).status_code, 200)
        compra = self.c001.compras.first()
        self.assertEqual(self.client.get(reverse("core:portal_compra", args=[compra.pk])).status_code, 200)
        r = self.client.get(reverse("core:portal_ciclo", args=[self.c001.pk, "20260920200000"]))
        self.assertContains(r, "S/ 201.90")
        self.assertContains(r, "Intereses por mora")  # la mora ya pagada aparece como ítem separado
        self.assertContains(r, "S/ 0.08")
        r = self.client.get(reverse("core:portal_comprobante", args=[self.pago.pk]))
        self.assertContains(r, "S/ 201.98")

    def test_no_ve_cuentas_compras_ni_comprobantes_ajenos(self):
        ajena = self.c002.compras.first()
        urls = [
            reverse("core:portal_cuenta", args=[self.c002.pk]),
            reverse("core:portal_compra", args=[ajena.pk]),
            reverse("core:portal_ciclo", args=[self.c002.pk, "20260920200000"]),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(Auditoria.objects.filter(evento="ACCESO_DENEGADO", usuario=self.carmen).count(), 3)

    def test_cliente_no_puede_operar_como_negocio(self):
        for url in (reverse("creditos:nueva_venta"), reverse("clientes:lista"), reverse("creditos:pago", args=[self.c001.pk])):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)
        r = self.client.post(reverse("creditos:pago", args=[self.c001.pk]), {"importe": "1"})
        self.assertEqual(r.status_code, 403)

    def test_cliente_con_cuentas_en_dos_tiendas(self):
        otra = crear_tienda(nombre="Pollería El Sabor")
        cuenta_otra = crear_cuenta(otra, usuario=self.carmen)
        crear_condicion(cuenta_otra)
        r = self.client.get(reverse("core:portal"))
        self.assertEqual(len(r.context["tarjetas"]), 2)

    def test_usuario_sin_cuentas_no_entra_al_portal(self):
        self.client.force_login(crear_usuario("nadie@x.pe"))
        self.assertEqual(self.client.get(reverse("core:portal")).status_code, 403)
