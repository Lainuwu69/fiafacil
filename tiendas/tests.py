"""Pruebas de la fase 2: restricciones de Tienda, Artículo y Membresía en PostgreSQL."""

from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase

from core.fabricas_prueba import crear_articulo, crear_tienda, crear_usuario
from core.modelos_base import OperacionNoPermitida
from cuentas.models import Membresia
from tiendas.models import Tienda


class TiendaTests(TestCase):
    def test_codigo_correlativo_T001_T002(self):
        t1 = crear_tienda()
        t2 = crear_tienda(nombre="Panadería San Juan", giro="Panadería")
        self.assertEqual((t1.codigo, t2.codigo), ("T001", "T002"))

    def test_registro_nace_pendiente(self):
        t = Tienda.objects.create(nombre="Spa Lucía", giro="Spa", direccion="Jr. Lima 1")
        self.assertEqual(t.estado, Tienda.Estado.PENDIENTE)

    def test_ruc_debe_tener_11_digitos(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            crear_tienda(ruc="1045678901")  # 10 dígitos
        self.assertIsNone(crear_tienda(ruc="").ruc)  # vacío se guarda como nulo
        self.assertEqual(crear_tienda(ruc="10456789012").ruc, "10456789012")

    def test_estado_invalido_rechazado_por_bd(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            crear_tienda(estado="CERRADA")

    def test_baja_logica_no_borrado_fisico(self):
        """RN09: una tienda no se elimina; se marca INACTIVA."""
        t = crear_tienda()
        with self.assertRaises(OperacionNoPermitida):
            t.delete()
        self.assertTrue(Tienda.objects.filter(pk=t.pk).exists())


class ArticuloTests(TestCase):
    def setUp(self):
        self.tienda = crear_tienda()

    def test_precios_deben_ser_positivos(self):
        for campo in ("precio_contado", "precio_credito"):
            with self.subTest(campo=campo), self.assertRaises(IntegrityError), transaction.atomic():
                crear_articulo(self.tienda, **{campo: Decimal("0.00")})

    def test_al_menos_una_modalidad(self):
        """RN11: el artículo debe venderse a fin de mes, en cuotas o de ambas formas."""
        with self.assertRaises(IntegrityError), transaction.atomic():
            crear_articulo(self.tienda, permite_mensual=False, permite_cuotas=False)

    def test_imagen_obligatoria_en_bd(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            crear_articulo(self.tienda, imagen="")

    def test_proveedor_y_marca_opcionales(self):
        a = crear_articulo(self.tienda, proveedor="", marca="")
        self.assertEqual((a.proveedor, a.marca), ("", ""))


class MembresiaTests(TestCase):
    def test_misma_membresia_no_se_duplica(self):
        u, t = crear_usuario(), crear_tienda()
        Membresia.objects.create(usuario=u, tienda=t, rol=Membresia.Rol.NEGOCIO)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Membresia.objects.create(usuario=u, tienda=t, rol=Membresia.Rol.NEGOCIO)

    def test_un_usuario_puede_ser_negocio_en_una_tienda_y_cliente_en_otra(self):
        u = crear_usuario()
        t1, t2 = crear_tienda(), crear_tienda(nombre="Pollería El Sabor", giro="Pollería")
        Membresia.objects.create(usuario=u, tienda=t1, rol=Membresia.Rol.NEGOCIO)
        Membresia.objects.create(usuario=u, tienda=t2, rol=Membresia.Rol.CLIENTE)
        self.assertEqual(u.membresias.count(), 2)
