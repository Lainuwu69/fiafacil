"""
Pruebas de las pantallas del negocio (fase 6): recorren el proceso financiero por HTTP,
como lo haría el usuario en el navegador, y verifican las API JSON de cálculo en vivo.
"""

import io
import json
import uuid
from datetime import date
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from clientes.models import CuentaCliente
from core.constantes import TipoTasa
from core.fabricas_prueba import crear_articulo, crear_condicion, crear_cuenta, crear_tienda, crear_usuario, lima
from core.models import Auditoria
from creditos import servicios as s
from creditos.models import Compra, EstadoCuenta, Obligacion, Pago
from cuentas.models import Membresia
from tiendas.models import Articulo


def imagen_png(nombre="foto.png", tam=(10, 10)):
    buf = io.BytesIO()
    Image.new("RGB", tam, (15, 118, 110)).save(buf, "PNG")
    return SimpleUploadedFile(nombre, buf.getvalue(), content_type="image/png")


class BaseVistas(TestCase):
    def setUp(self):
        self.usuario = crear_usuario()
        self.tienda = crear_tienda()
        Membresia.objects.create(usuario=self.usuario, tienda=self.tienda, rol="NEGOCIO")
        self.articulo = crear_articulo(self.tienda)
        self.client.force_login(self.usuario)

    def post_json(self, url, datos):
        return self.client.post(url, json.dumps(datos), content_type="application/json").json()


@override_settings(MEDIA_ROOT="media_pruebas")
class CatalogoTests(BaseVistas):
    def tearDown(self):
        import shutil
        shutil.rmtree("media_pruebas", ignore_errors=True)

    def datos(self, **cambios):
        d = {"descripcion": "Arroz extra 5 kg", "marca": "Costeño", "proveedor": "", "unidad": "PAQUETE",
             "precio_contado": "18.50", "precio_credito": "19.90", "permite_mensual": "on", "imagen": imagen_png()}
        d.update(cambios)
        return d

    def test_alta_con_imagen_y_auditoria(self):
        r = self.client.post(reverse("tiendas:articulo_nuevo"), self.datos())
        self.assertRedirects(r, reverse("tiendas:catalogo"))
        a = Articulo.objects.get(descripcion="Arroz extra 5 kg")
        self.assertEqual((a.tienda, a.precio_credito), (self.tienda, Decimal("19.90")))
        self.assertTrue(Auditoria.objects.filter(evento="ALTA", objeto_id=str(a.pk)).exists())

    def test_imagen_obligatoria_tamano_y_formato(self):
        sin = self.datos()
        sin.pop("imagen")
        self.assertContains(self.client.post(reverse("tiendas:articulo_nuevo"), sin), "obligatoria")
        with self.settings(IMAGEN_MAX_BYTES=50):
            self.assertContains(self.client.post(reverse("tiendas:articulo_nuevo"), self.datos()), "el máximo es")
        texto = SimpleUploadedFile("x.png", b"no soy una imagen", content_type="image/png")
        r = self.client.post(reverse("tiendas:articulo_nuevo"), self.datos(imagen=texto))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Articulo.objects.filter(descripcion="Arroz extra 5 kg").exists())

    def test_baja_logica_y_articulo_ajeno_404(self):
        self.client.post(reverse("tiendas:articulo_estado", args=[self.articulo.pk]))
        self.articulo.refresh_from_db()
        self.assertFalse(self.articulo.activo)
        ajeno = crear_articulo(crear_tienda(nombre="Otra"))
        self.assertEqual(self.client.get(reverse("tiendas:articulo_editar", args=[ajeno.pk])).status_code, 404)
        self.assertTrue(Auditoria.objects.filter(evento="ACCESO_DENEGADO").exists())


class ClientesTests(BaseVistas):
    def datos(self, **cambios):
        d = {"c-tipo_documento": "DNI", "c-documento": "45678912", "c-nombre": "Carmen Quispe Rojas", "c-telefono": "",
             "c-correo": "", "c-direccion": "", "c-moneda": "PEN",
             "k-tasa_tipo": "NOMINAL", "k-tasa_porcentaje": "24", "k-tasa_periodo": "360", "k-tasa_capitalizacion": "30",
             "k-mora_tipo": "EFECTIVA", "k-mora_porcentaje": "3", "k-mora_periodo": "360", "k-mora_capitalizacion": "",
             "k-limite": "1000", "k-plazo_max": "3", "k-dia_corte": "20", "k-hora_corte": "20:00:00", "k-dia_pago": "26",
             "k-vigente_desde": "2026-09-01T00:00:00"}
        d.update(cambios)
        return d

    def test_alta_con_tasas_en_porcentaje(self):
        r = self.client.post(reverse("clientes:nuevo"), self.datos())
        cuenta = CuentaCliente.objects.get(documento="45678912")
        self.assertRedirects(r, reverse("clientes:detalle", args=[cuenta.pk]))
        c = cuenta.condicion_vigente()
        self.assertEqual((c.tasa_valor, c.tasa_capitalizacion, c.mora_valor), (Decimal("0.24"), 30, Decimal("0.03")))
        detalle = self.client.get(reverse("clientes:detalle", args=[cuenta.pk]))
        self.assertContains(detalle, "2.0000000 %")  # TEM
        self.assertContains(detalle, "26.8241795 %")  # TEA

    def test_validaciones_del_formulario(self):
        r = self.client.post(reverse("clientes:nuevo"), self.datos(**{"c-documento": "123", "k-dia_pago": "15"}))
        self.assertContains(r, "El DNI tiene 8 dígitos")
        self.assertContains(r, "debe ser posterior al día de corte")
        self.assertFalse(CuentaCliente.objects.exists())

    def test_api_tasa_equivalente(self):
        url = reverse("clientes:api_tasa")
        r = self.post_json(url, {"tipo": "NOMINAL", "porcentaje": "24", "periodo": 360, "capitalizacion": 30})
        self.assertEqual((r["tem_texto"], r["tea_texto"]), ("2.0000000 %", "26.8241795 %"))
        r = self.post_json(url, {"tipo": "NOMINAL", "porcentaje": "24", "periodo": 360, "capitalizacion": ""})
        self.assertIn("diaria", r["supuestos"][0])
        self.assertFalse(self.post_json(url, {"tipo": "EFECTIVA", "porcentaje": "abc"})["ok"])

    def test_nueva_version_de_condiciones(self):
        self.client.post(reverse("clientes:nuevo"), self.datos())
        cuenta = CuentaCliente.objects.get()
        d = {k: v for k, v in self.datos().items() if k.startswith("k-")}
        d.update({"k-tasa_porcentaje": "30", "k-vigente_desde": ""})
        self.client.post(reverse("clientes:condicion", args=[cuenta.pk]), d)
        self.assertEqual(cuenta.condicion_vigente().version, 2)
        self.assertEqual(cuenta.condiciones.count(), 2)

    def test_acceso_al_portal_del_cliente(self):
        self.client.post(reverse("clientes:nuevo"), self.datos())
        cuenta = CuentaCliente.objects.get()
        self.client.post(reverse("clientes:acceso", args=[cuenta.pk]), {"email": "carmen@cliente.pe", "password": "Carmen-Portal-2026"})
        cuenta.refresh_from_db()
        self.assertEqual(cuenta.usuario.email, "carmen@cliente.pe")
        self.assertTrue(Membresia.objects.filter(usuario=cuenta.usuario, tienda=self.tienda, rol="CLIENTE").exists())

    def test_cliente_de_otra_tienda_404(self):
        ajena = crear_cuenta(crear_tienda(nombre="Otra"))
        self.assertEqual(self.client.get(reverse("clientes:detalle", args=[ajena.pk])).status_code, 404)


class ProcesoFinancieroTests(BaseVistas):
    """Juego A y juego B por las pantallas: venta → estado → pago → comprobante."""

    def setUp(self):
        super().setUp()
        self.c001 = crear_cuenta(self.tienda)
        crear_condicion(self.c001)
        self.c002 = crear_cuenta(self.tienda, documento="87654321", nombre="Pedro Huamán")
        crear_condicion(self.c002, tasa_tipo=TipoTasa.NOMINAL, tasa_capitalizacion=30)

    def vender(self, cuenta, cantidad, fecha, modalidad="MENSUAL", n="", clave=None):
        return self.client.post(reverse("creditos:nueva_venta"), {
            "cuenta": cuenta.pk, "fecha_compra": fecha, "modalidad": modalidad, "n_cuotas": n,
            "articulo": [self.articulo.pk], "cantidad": [str(cantidad)], "clave": clave or str(uuid.uuid4()),
        })

    def test_simulacion_en_vivo_juego_b(self):
        r = self.post_json(reverse("creditos:api_simular"), {
            "cuenta": str(self.c002.pk), "fecha_compra": "2026-09-15T10:00", "modalidad": "CUOTAS", "n_cuotas": 3,
            "lineas": [{"articulo_id": str(self.articulo.pk), "cantidad": "600"}]})
        self.assertTrue(r["valida"])
        self.assertEqual((r["cuotas"]["capital_con_gracia"], r["cuotas"]["cuota"], r["cuotas"]["total"]), ("604.37", "209.57", "628.71"))
        self.assertEqual((r["fecha_pago"], r["disponible_despues"]), ("26/09/2026", "395.63"))
        self.assertEqual(r["tcea"], "26.8273729 %")
        self.assertEqual(Compra.objects.count(), 0)  # simular no graba

    def test_simulacion_muestra_el_exceso_de_limite(self):
        r = self.post_json(reverse("creditos:api_simular"), {
            "cuenta": str(self.c001.pk), "fecha_compra": "2026-09-15T10:00", "modalidad": "MENSUAL",
            "lineas": [{"articulo_id": str(self.articulo.pk), "cantidad": "1000.01"}]})
        self.assertFalse(r["valida"])
        self.assertIn("Disponible: S/ 1,000.00; se necesita: S/ 1,000.01", r["errores"][0])

    def test_venta_doble_clic_no_duplica(self):
        clave = str(uuid.uuid4())
        r1 = self.vender(self.c001, 120, "2026-09-05T10:00", clave=clave)
        r2 = self.vender(self.c001, 120, "2026-09-05T10:00", clave=clave)
        compra = Compra.objects.get()
        self.assertRedirects(r1, reverse("creditos:compra", args=[compra.pk]))
        self.assertRedirects(r2, reverse("creditos:compra", args=[compra.pk]))

    def test_juego_a_completo_por_pantallas(self):
        self.vender(self.c001, 120, "2026-09-05T10:00")
        self.vender(self.c001, 80, "2026-09-18T10:00")
        self.vender(self.c001, 50, "2026-09-21T10:00")
        url_ciclo = reverse("creditos:ciclo", args=[self.c001.pk, "20260920200000"])
        vista = self.client.get(url_ciclo, {"al": "2026-10-01"})
        self.assertContains(vista, "S/ 201.90")
        self.assertContains(vista, "Intereses por mora")  # ítem separado, proyectado
        self.assertContains(vista, "S/ 0.08")
        self.client.post(url_ciclo)  # generar (el corte ya se cumplió)
        self.assertEqual(EstadoCuenta.objects.get().total, Decimal("201.90"))

        ids = [str(o.pk) for o in Obligacion.objects.filter(cuenta=self.c001, vencimiento=date(2026, 9, 26))]
        liq = self.post_json(reverse("creditos:api_calcular_pago", args=[self.c001.pk]), {"obligaciones": ids, "fecha": "2026-10-01"})
        self.assertEqual((liq["mora"], liq["interes"], liq["capital"], liq["total"]), ("0.08", "1.90", "200.00", "201.98"))

        url_pago = reverse("creditos:pago", args=[self.c001.pk])
        r = self.client.post(url_pago, {"obligacion": ids, "fecha_efectiva": "2026-10-01", "importe": "150.00", "clave": str(uuid.uuid4())})
        self.assertContains(r, "No se aceptan pagos parciales")
        r = self.client.post(url_pago, {"obligacion": ids, "fecha_efectiva": "2026-10-01", "importe": "201.98", "clave": str(uuid.uuid4())})
        pago = Pago.objects.get()
        self.assertRedirects(r, reverse("creditos:comprobante", args=[pago.pk]))
        comprobante = self.client.get(reverse("creditos:comprobante", args=[pago.pk]))
        self.assertContains(comprobante, "S/ 201.98")
        self.assertContains(comprobante, "000001")
        self.assertEqual(s.disponible(self.c001), Decimal("950.00"))

    def test_panel_indicadores_y_flujo(self):
        self.vender(self.c002, 600, "2026-09-15T10:00", modalidad="CUOTAS", n=3)
        r = self.client.get(reverse("core:panel"))
        self.assertEqual(r.status_code, 200)
        ind = r.context["indicadores"]["PEN"]
        self.assertEqual(ind["capital"], Decimal("604.37"))
        self.assertEqual(ind["total"], Decimal("628.71"))
        self.assertContains(r, "Flujo de caja proyectado")

    def test_auditoria_solo_de_mi_tienda(self):
        Auditoria.registrar(Auditoria.Evento.ALTA, "Evento de otra tienda", tienda=crear_tienda(nombre="Otra"))
        self.vender(self.c001, 10, "2026-09-05T10:00")
        r = self.client.get(reverse("core:auditoria"))
        self.assertContains(r, "Compra al crédito")
        self.assertNotContains(r, "Evento de otra tienda")


class AyudaPorCampoTests(TestCase):
    """Rúbrica (punto 9d): cada campo de cada formulario tiene ayuda con ejemplo."""

    def test_todos_los_campos_tienen_help_text(self):
        from clientes.forms import AccesoForm, CondicionForm, CuentaForm
        from cuentas.forms import CambioClaveForm, LoginForm, RegistroForm
        from tiendas.forms import ArticuloForm

        formularios = (RegistroForm(), LoginForm(), ArticuloForm(), CuentaForm(), CondicionForm(), AccesoForm(),
                       CambioClaveForm(user=None))
        for form in formularios:
            for campo in form:
                with self.subTest(formulario=form.__class__.__name__, campo=campo.name):
                    self.assertTrue(campo.help_text, f"{form.__class__.__name__}.{campo.name} no tiene ayuda")
