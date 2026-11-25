"""
Pruebas de la fase 1: el proyecto base quedó configurado como pide el diseño.

Las pruebas financieras (juegos A y B, frontera y reglas) van en creditos/tests.py.
"""

from datetime import date, datetime
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.db import IntegrityError, connection
from django.test import TestCase
from django.utils import formats, timezone, translation


class ConfiguracionBaseTests(TestCase):
    def test_base_de_datos_es_postgresql(self):
        self.assertEqual(connection.vendor, "postgresql")

    def test_zona_horaria_de_lima(self):
        """RN03: el corte se evalúa en hora de Lima (UTC-5, sin horario de verano)."""
        self.assertEqual(settings.TIME_ZONE, "America/Lima")
        self.assertTrue(settings.USE_TZ)
        momento = timezone.make_aware(datetime(2026, 9, 20, 20, 0))
        self.assertEqual(momento.utcoffset().total_seconds(), -5 * 3600)

    def test_hora_de_lima_se_conserva_al_guardar_y_leer(self):
        """La base guarda instantes absolutos (timestamptz): 20:00 en Lima son 01:00 UTC
        del día siguiente, y al leerlos se recupera exactamente 20:00 en Lima."""
        corte = timezone.make_aware(datetime(2026, 9, 20, 20, 0, 0))
        with connection.cursor() as cursor:
            cursor.execute("SELECT %s::timestamptz, (%s::timestamptz AT TIME ZONE 'UTC')", [corte, corte])
            leido, en_utc = cursor.fetchone()
        self.assertEqual(timezone.localtime(leido), corte)
        self.assertEqual(timezone.localtime(leido).hour, 20)
        self.assertEqual(en_utc, datetime(2026, 9, 21, 1, 0, 0))

    def test_usuario_personalizado(self):
        self.assertEqual(settings.AUTH_USER_MODEL, "cuentas.Usuario")


class FormatosPeruanosTests(TestCase):
    def test_punto_decimal_y_fecha_dd_mm_aaaa(self):
        with translation.override("es-pe"):
            self.assertEqual(formats.get_format("DECIMAL_SEPARATOR"), ".")
            self.assertEqual(formats.date_format(date(2026, 9, 15)), "15/09/2026")
            self.assertEqual(formats.number_format(Decimal("1250.5"), 2), "1250.50")
            self.assertEqual(
                formats.number_format(Decimal("1250.5"), 2, force_grouping=True), "1,250.50"
            )

    def test_acepta_fechas_escritas_dd_mm_aaaa(self):
        with translation.override("es-pe"):
            self.assertIn("%d/%m/%Y", formats.get_format("DATE_INPUT_FORMATS"))


class UsuarioPorCorreoTests(TestCase):
    def setUp(self):
        self.Usuario = get_user_model()

    def test_crea_usuario_con_uuid_y_correo_en_minusculas(self):
        u = self.Usuario.objects.create_user("Rosa@Bodega.PE", "Fiafacil-2026", nombres="Rosa")
        self.assertEqual(u.email, "rosa@bodega.pe")
        self.assertEqual(len(str(u.id)), 36)  # UUID
        self.assertNotEqual(u.password, "Fiafacil-2026")  # se guarda el hash, no la clave

    def test_login_por_correo_sin_distinguir_mayusculas(self):
        self.Usuario.objects.create_user("rosa@bodega.pe", "Fiafacil-2026", nombres="Rosa")
        self.assertIsNotNone(authenticate(username="ROSA@bodega.pe", password="Fiafacil-2026"))
        self.assertIsNone(authenticate(username="rosa@bodega.pe", password="clave-incorrecta"))

    def test_correo_unico(self):
        self.Usuario.objects.create_user("rosa@bodega.pe", "x-Fiafacil-1", nombres="Rosa")
        with self.assertRaises(IntegrityError):
            self.Usuario.objects.create_user("rosa@bodega.pe", "x-Fiafacil-2", nombres="Otra")

    def test_superusuario_es_administrador_de_plataforma(self):
        admin = self.Usuario.objects.create_superuser("admin@fiafacil.pe", "Fiafacil-2026", nombres="Admin")
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)


class AyudaTests(TestCase):
    """Fase 8 (punto 9d): ayuda general y canales de soporte."""

    def test_ayuda_publica_con_secciones_y_formulas(self):
        from django.urls import reverse

        r = self.client.get(reverse("core:ayuda"))
        self.assertEqual(r.status_code, 200)
        for texto in ("Primeros pasos", "Perfiles", "Cómo se calcula", "Preguntas frecuentes", "Glosario", "Soporte técnico",
                      "604.37", "209.57", "201.98", "26.8241795 %"):
            with self.subTest(texto=texto):
                self.assertContains(r, texto)

    def test_canales_de_soporte_configurables(self):
        from django.urls import reverse

        with self.settings(SOPORTE_WHATSAPP="51911222333", SOPORTE_CORREO="ayuda@ejemplo.pe"):
            r = self.client.get(reverse("core:ayuda"))
        self.assertContains(r, "https://wa.me/51911222333")
        self.assertContains(r, "mailto:ayuda@ejemplo.pe")

    def test_enlace_a_la_ayuda_en_login_y_menu(self):
        from django.urls import reverse

        self.assertContains(self.client.get(reverse("cuentas:login")), reverse("core:ayuda"))
        u = get_user_model().objects.create_user("x@x.pe", "Fiafacil-2026", nombres="X")
        self.client.force_login(u)
        self.assertContains(self.client.get(reverse("core:ayuda")), "Centro de ayuda")
