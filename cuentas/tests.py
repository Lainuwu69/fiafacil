"""
Pruebas de la fase 5: registro, inicio de sesión, roles y separación por tienda.

Reproducen la secuencia obligatoria de la demo: registro de un usuario nuevo →
inicio de sesión con ese usuario → (activación por la plataforma) → acceso al negocio.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.fabricas_prueba import CLAVE_PRUEBA, crear_cuenta, crear_tienda, crear_usuario
from core.models import Auditoria
from cuentas.forms import MAX_INTENTOS
from cuentas.models import Membresia
from tiendas.models import Tienda

Usuario = get_user_model()

DATOS_REGISTRO = {
    "nombres": "Rosa", "apellidos": "Quispe", "email": "Nueva@Bodega.pe",
    "password1": "Bodega-Segura-2026", "password2": "Bodega-Segura-2026",
    "nombre_tienda": "Bodega La Esquina", "giro": "Bodega", "ruc": "", "direccion": "Jr. Junín 456",
    "telefono": "987654321", "acepta_privacidad": "on",
}


class RegistroTests(TestCase):
    def test_registro_crea_usuario_tienda_pendiente_y_membresia(self):
        r = self.client.post(reverse("cuentas:registro"), DATOS_REGISTRO)
        self.assertRedirects(r, reverse("cuentas:login"))
        u = Usuario.objects.get(email="nueva@bodega.pe")
        m = Membresia.objects.get(usuario=u)
        self.assertEqual((m.rol, m.tienda.estado, m.tienda.codigo), ("NEGOCIO", "PENDIENTE", "T001"))
        self.assertTrue(u.check_password("Bodega-Segura-2026"))
        self.assertTrue(Auditoria.objects.filter(evento="REGISTRO", usuario=u).exists())
        self.assertNotIn("_auth_user_id", self.client.session)  # no inicia sesión solo

    def test_correo_repetido_y_claves_distintas(self):
        crear_usuario("nueva@bodega.pe")
        datos = {**DATOS_REGISTRO, "password2": "Otra-Clave-2026"}
        r = self.client.post(reverse("cuentas:registro"), datos)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Ya existe un usuario con ese correo")
        self.assertContains(r, "Las contraseñas no coinciden")
        self.assertEqual(Tienda.objects.count(), 0)

    def test_contrasena_debil_y_ruc_invalido(self):
        datos = {**DATOS_REGISTRO, "password1": "12345678", "password2": "12345678", "ruc": "123"}
        r = self.client.post(reverse("cuentas:registro"), datos)
        self.assertContains(r, "El RUC debe tener 11 dígitos")
        self.assertEqual(Usuario.objects.count(), 0)

    def test_debe_aceptar_privacidad(self):
        datos = {k: v for k, v in DATOS_REGISTRO.items() if k != "acepta_privacidad"}
        r = self.client.post(reverse("cuentas:registro"), datos)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Usuario.objects.count(), 0)

    def test_cada_campo_del_registro_tiene_ayuda(self):
        r = self.client.get(reverse("cuentas:registro"))
        for campo in r.context["form"]:
            self.assertTrue(campo.help_text, f"El campo {campo.name} no tiene ayuda")
        self.assertContains(r, "bi-info-circle")


class LoginTests(TestCase):
    def setUp(self):
        self.usuario = crear_usuario("rosa@bodega.pe")
        self.tienda = crear_tienda()
        Membresia.objects.create(usuario=self.usuario, tienda=self.tienda, rol="NEGOCIO")

    def login(self, email="rosa@bodega.pe", clave=CLAVE_PRUEBA):
        return self.client.post(reverse("cuentas:login"), {"username": email, "password": clave})

    def test_login_correcto_y_auditado(self):
        r = self.login("ROSA@bodega.pe")
        self.assertRedirects(r, reverse("core:inicio"), fetch_redirect_response=False)
        self.assertEqual(self.client.get(reverse("core:inicio")).url, reverse("core:panel"))
        # El login queda en la auditoría de la tienda del usuario (la ve el negocio en su pantalla de auditoría).
        self.assertTrue(Auditoria.objects.filter(evento="LOGIN", usuario=self.usuario, tienda=self.tienda).exists())

    def test_login_fallido_auditado_sin_guardar_contrasena(self):
        r = self.login(clave="clave-mala")
        self.assertContains(r, "Correo o contraseña incorrectos")
        a = Auditoria.objects.get(evento="LOGIN_FALLIDO")
        self.assertEqual(a.datos, {"email": "rosa@bodega.pe"})
        self.assertNotIn("clave-mala", str(a.datos) + a.descripcion)

    def test_bloqueo_tras_intentos_fallidos(self):
        for _ in range(MAX_INTENTOS):
            self.login(clave="clave-mala")
        r = self.login()  # ahora con la clave correcta
        self.assertContains(r, "Demasiados intentos fallidos")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_solo_por_post(self):
        self.login()
        self.assertEqual(self.client.get(reverse("cuentas:logout")).status_code, 405)
        self.client.post(reverse("cuentas:logout"))
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertTrue(Auditoria.objects.filter(evento="LOGOUT").exists())

    def test_sin_sesion_redirige_al_login(self):
        r = self.client.get(reverse("core:panel"))
        self.assertRedirects(r, f"{reverse('cuentas:login')}?next={reverse('core:panel')}")


class CambioClaveTests(TestCase):
    def setUp(self):
        self.usuario = crear_usuario("rosa@bodega.pe")
        self.client.force_login(self.usuario)
        self.url = reverse("cuentas:cambiar_clave")

    def test_cambiar_contrasena_mantiene_la_sesion_y_se_audita(self):
        r = self.client.post(self.url, {"old_password": CLAVE_PRUEBA, "new_password1": "Bodega-Nueva-2027",
                                        "new_password2": "Bodega-Nueva-2027"})
        self.assertRedirects(r, reverse("core:inicio"), fetch_redirect_response=False)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password("Bodega-Nueva-2027"))
        self.assertIn("_auth_user_id", self.client.session)  # no la expulsa
        self.assertTrue(Auditoria.objects.filter(evento="CAMBIO_CLAVE", usuario=self.usuario).exists())

    def test_exige_la_contrasena_actual_y_una_nueva_segura(self):
        r = self.client.post(self.url, {"old_password": "otra", "new_password1": "12345678", "new_password2": "12345678"})
        self.assertEqual(r.status_code, 200)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password(CLAVE_PRUEBA))

    def test_cada_campo_tiene_ayuda(self):
        r = self.client.get(self.url)
        for campo in r.context["form"]:
            self.assertTrue(campo.help_text)


class FlujoDemoTests(TestCase):
    """Registro → login → tienda pendiente → la plataforma la activa → acceso al panel."""

    def test_flujo_completo(self):
        admin = Usuario.objects.create_superuser("admin@fiafacil.pe", CLAVE_PRUEBA, nombres="Admin")
        self.client.post(reverse("cuentas:registro"), DATOS_REGISTRO)
        self.client.post(reverse("cuentas:login"), {"username": "nueva@bodega.pe", "password": "Bodega-Segura-2026"})
        r = self.client.get(reverse("core:panel"))
        self.assertRedirects(r, reverse("core:tienda_pendiente"))

        plataforma = self.client_class()
        plataforma.force_login(admin)
        tienda = Tienda.objects.get(nombre="Bodega La Esquina")
        plataforma.post(reverse("tiendas:cambiar_estado", args=[tienda.pk, "activar"]))
        tienda.refresh_from_db()
        self.assertEqual(tienda.estado, "ACTIVA")
        self.assertIsNotNone(tienda.fecha_activacion)
        self.assertTrue(Auditoria.objects.filter(evento="ACTIVACION", tienda=tienda).exists())

        self.assertEqual(self.client.get(reverse("core:panel")).status_code, 200)

    def test_tienda_dada_de_baja_bloquea_al_negocio(self):
        u, t = crear_usuario(), crear_tienda(estado="INACTIVA")
        Membresia.objects.create(usuario=u, tienda=t, rol="NEGOCIO")
        self.client.force_login(u)
        self.assertEqual(self.client.get(reverse("core:panel")).status_code, 403)


class RolesTests(TestCase):
    def setUp(self):
        self.tienda = crear_tienda()
        self.negocio = crear_usuario("rosa@bodega.pe")
        Membresia.objects.create(usuario=self.negocio, tienda=self.tienda, rol="NEGOCIO")
        self.cliente = crear_usuario("carmen@cliente.pe")
        crear_cuenta(self.tienda, usuario=self.cliente)
        Membresia.objects.create(usuario=self.cliente, tienda=self.tienda, rol="CLIENTE")

    def test_cliente_no_entra_al_negocio_ni_a_la_plataforma(self):
        self.client.force_login(self.cliente)
        self.assertEqual(self.client.get(reverse("core:inicio")).url, reverse("core:portal"))
        self.assertEqual(self.client.get(reverse("core:panel")).status_code, 403)
        self.assertEqual(self.client.get(reverse("tiendas:plataforma")).status_code, 403)
        self.assertEqual(Auditoria.objects.filter(evento="ACCESO_DENEGADO", usuario=self.cliente).count(), 2)

    def test_negocio_no_entra_a_la_plataforma_ni_activa_tiendas(self):
        pendiente = crear_tienda(nombre="Otra", estado="PENDIENTE")
        self.client.force_login(self.negocio)
        self.assertEqual(self.client.get(reverse("tiendas:plataforma")).status_code, 403)
        self.assertEqual(self.client.post(reverse("tiendas:cambiar_estado", args=[pendiente.pk, "activar"])).status_code, 403)
        pendiente.refresh_from_db()
        self.assertEqual(pendiente.estado, "PENDIENTE")

    def test_baja_y_reactivacion_de_tienda(self):
        admin = Usuario.objects.create_superuser("admin@fiafacil.pe", CLAVE_PRUEBA, nombres="Admin")
        self.client.force_login(admin)
        self.client.post(reverse("tiendas:cambiar_estado", args=[self.tienda.pk, "baja"]))
        self.tienda.refresh_from_db()
        self.assertEqual(self.tienda.estado, "INACTIVA")
        self.client.post(reverse("tiendas:cambiar_estado", args=[self.tienda.pk, "reactivar"]))
        self.tienda.refresh_from_db()
        self.assertEqual(self.tienda.estado, "ACTIVA")
        self.assertTrue(Tienda.objects.filter(pk=self.tienda.pk).exists())  # baja lógica

    def test_no_se_puede_cambiar_a_una_tienda_ajena(self):
        ajena = crear_tienda(nombre="Ajena")
        m_ajena = Membresia.objects.create(usuario=crear_usuario("otro@x.pe"), tienda=ajena, rol="NEGOCIO")
        self.client.force_login(self.negocio)
        self.client.post(reverse("cuentas:cambiar_tienda"), {"membresia": str(m_ajena.pk)})
        r = self.client.get(reverse("core:panel"))
        self.assertEqual(r.wsgi_request.tienda, self.tienda)

    def test_usuario_con_dos_roles_elige_tienda(self):
        otra = crear_tienda(nombre="Pollería El Sabor")
        m_cliente = Membresia.objects.create(usuario=self.negocio, tienda=otra, rol="CLIENTE")
        self.client.force_login(self.negocio)
        self.client.post(reverse("cuentas:cambiar_tienda"), {"membresia": str(m_cliente.pk)})
        r = self.client.get(reverse("core:portal"))
        self.assertEqual(r.wsgi_request.tienda, otra)
        # Al entrar al panel vuelve solo a su tienda de negocio.
        r = self.client.get(reverse("core:panel"))
        self.assertEqual((r.status_code, r.wsgi_request.tienda), (200, self.tienda))
