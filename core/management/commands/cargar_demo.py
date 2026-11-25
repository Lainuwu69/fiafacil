"""
Carga los datos de demostración de FíaFácil (juegos A y B del informe, sección 3.4).

Uso:
    python manage.py cargar_demo
        Usuarios, tienda T001 "Bodega Doña Rosa", catálogo y clientes C001 (juego A) y
        C002 (juego B) con sus condiciones, SIN operaciones: para hacer la demo desde cero.

    python manage.py cargar_demo --con-operaciones
        Además registra las compras, estados de cuenta y pagos de ambos juegos, para
        mostrar un panel, un portal y una auditoría con datos.

    python manage.py cargar_demo --reiniciar --si [--con-operaciones]
        BORRA TODOS los datos de la base (usuarios, tiendas y operaciones) y vuelve a cargar
        la demo. Solo para preparar la exposición; pide --si como confirmación explícita.

Usuarios (clave Fiafacil-2026):
    admin@fiafacil.pe   administrador de la plataforma
    rosa@bodega.pe      negocio, tienda T001 "Bodega Doña Rosa"
    carmen@cliente.pe   cliente, portal de la cuenta C001

Las operaciones se registran con los MISMOS servicios que usan las pantallas
(registrar_compra, generar_estado, registrar_pago): no se escriben importes a mano.
"""

import io
import uuid
from datetime import date, datetime, time
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from PIL import Image, ImageDraw

from clientes.models import CondicionCredito, CuentaCliente
from clientes.servicios import abrir_cuenta, dar_acceso_cliente
from core.models import Auditoria
from creditos import servicios as s
from creditos.models import Anulacion, Compra, DetalleCompra, EstadoCuenta, EstadoDetalle, Obligacion, Pago, PagoAplicacion
from cuentas.models import Membresia
from tiendas.models import Articulo, Tienda

CLAVE = "Fiafacil-2026"
Usuario = get_user_model()


def lima(*args):
    return timezone.make_aware(datetime(*args))


def imagen(texto, color):
    """Imagen simple generada (no se descarga nada): un bloque de color con el nombre del artículo."""
    lienzo = Image.new("RGB", (480, 320), color)
    ImageDraw.Draw(lienzo).text((24, 140), texto, fill=(255, 255, 255))
    buf = io.BytesIO()
    lienzo.save(buf, "PNG")
    return ContentFile(buf.getvalue())


CONDICION_COMUN = {
    "mora_tipo": "EFECTIVA", "mora_valor": Decimal("0.03"), "mora_periodo": 360, "mora_capitalizacion": None,
    "limite": Decimal("1000.00"), "plazo_max": 3, "dia_corte": 20, "hora_corte": time(20, 0), "dia_pago": 26,
}
JUEGO_A = {"tasa_tipo": "EFECTIVA", "tasa_valor": Decimal("0.24"), "tasa_periodo": 360, "tasa_capitalizacion": None, **CONDICION_COMUN}
JUEGO_B = {"tasa_tipo": "NOMINAL", "tasa_valor": Decimal("0.24"), "tasa_periodo": 360, "tasa_capitalizacion": 30, **CONDICION_COMUN}
VIGENTE_DESDE = (2026, 9, 1, 0, 0)

ARTICULOS = [
    # descripción, unidad, marca, contado, lista, mensual, cuotas, color
    ("Consumo general", "UNIDAD", "", "1.00", "1.00", True, True, (15, 118, 110)),
    ("Arroz extra 5 kg", "PAQUETE", "Costeño", "18.50", "19.90", True, False, (180, 120, 40)),
    ("Aceite vegetal 1 L", "UNIDAD", "Primor", "9.80", "10.50", True, False, (200, 160, 20)),
    ("Balón de gas 10 kg", "UNIDAD", "Solgas", "48.00", "52.00", True, True, (40, 90, 160)),
]


class Command(BaseCommand):
    help = "Carga los datos de demostración (juegos A y B). Use --con-operaciones para registrar compras, estados y pagos."

    def add_arguments(self, parser):
        parser.add_argument("--con-operaciones", action="store_true", help="Registra las compras, estados y pagos de los juegos A y B.")
        parser.add_argument("--reiniciar", action="store_true", help="Borra TODOS los datos antes de cargar (requiere --si).")
        parser.add_argument("--si", action="store_true", help="Confirma el borrado de --reiniciar.")

    def handle(self, *args, **op):
        if op["reiniciar"]:
            if not op["si"]:
                raise CommandError("--reiniciar borra TODOS los usuarios, tiendas y operaciones. Si está seguro, agregue --si.")
            self.reiniciar()
        with transaction.atomic():
            admin, rosa, carmen = self.usuarios()
            tienda = self.tienda(rosa)
            articulos = self.catalogo(tienda)
            c001, c002 = self.clientes(tienda, rosa, carmen)
        self.stdout.write(self.style.SUCCESS(f"Demo lista: {tienda.codigo} «{tienda.nombre}», clientes {c001.codigo} y {c002.codigo}."))
        if op["con_operaciones"]:
            if c001.compras.exists() or c002.compras.exists():
                self.stdout.write(self.style.WARNING("Las cuentas ya tienen operaciones; no se registran de nuevo."))
            else:
                self.operaciones(rosa, tienda, articulos["Consumo general"], c001, c002)
        self.stdout.write(f"Usuarios (clave {CLAVE}): admin@fiafacil.pe · rosa@bodega.pe · carmen@cliente.pe")

    # -- borrado total (solo con --reiniciar --si) -------------------------------------------
    def reiniciar(self):
        # Se usa QuerySet.delete(), que no pasa por el bloqueo de borrado de los modelos:
        # es una operación administrativa explícita para preparar la exposición.
        for modelo in (Anulacion, PagoAplicacion, Pago, EstadoDetalle, EstadoCuenta, Obligacion, DetalleCompra, Compra,
                       CondicionCredito, CuentaCliente, Articulo, Membresia, Auditoria, Tienda, Session):
            modelo.objects.all().delete()
        Usuario.objects.all().delete()
        self.stdout.write(self.style.WARNING("Se borraron todos los datos."))

    # -- datos maestros -----------------------------------------------------------------------
    def usuarios(self):
        def obtener(email, nombres, apellidos="", **extra):
            u = Usuario.objects.filter(email__iexact=email).first()
            if u is None:
                creador = Usuario.objects.create_superuser if extra.get("is_staff") else Usuario.objects.create_user
                u = creador(email, CLAVE, nombres=nombres, apellidos=apellidos)
            return u

        return (
            obtener("admin@fiafacil.pe", "Administrador", "FíaFácil", is_staff=True),
            obtener("rosa@bodega.pe", "Rosa", "Quispe Torres"),
            obtener("carmen@cliente.pe", "Carmen", "Quispe Rojas"),
        )

    def tienda(self, rosa):
        tienda = Tienda.objects.filter(nombre="Bodega Doña Rosa").first()
        if tienda is None:
            tienda = Tienda.objects.create(
                nombre="Bodega Doña Rosa", giro="Bodega", direccion="Av. Los Álamos 123, San Juan de Lurigancho",
                telefono="987654321", estado=Tienda.Estado.ACTIVA, fecha_activacion=timezone.now(),
            )
        Membresia.objects.get_or_create(usuario=rosa, tienda=tienda, rol=Membresia.Rol.NEGOCIO)
        return tienda

    def catalogo(self, tienda):
        salida = {}
        for desc, unidad, marca, contado, lista, mensual, cuotas, color in ARTICULOS:
            a = Articulo.objects.filter(tienda=tienda, descripcion=desc).first()
            if a is None:
                a = Articulo(tienda=tienda, descripcion=desc, unidad=unidad, marca=marca, precio_contado=Decimal(contado),
                             precio_credito=Decimal(lista), permite_mensual=mensual, permite_cuotas=cuotas)
                a.imagen.save(f"demo-{desc.split()[0].lower()}.png", imagen(desc, color), save=True)
            salida[desc] = a
        return salida

    def clientes(self, tienda, rosa, carmen):
        def cuenta(documento, nombre, condicion, telefono):
            c = CuentaCliente.objects.filter(tienda=tienda, documento=documento, moneda="PEN").first()
            if c is None:
                c = abrir_cuenta(tienda, rosa, {"tipo_documento": "DNI", "documento": documento, "nombre": nombre,
                                                "telefono": telefono, "moneda": "PEN"},
                                 condicion, vigente_desde=lima(*VIGENTE_DESDE))
            return c

        c001 = cuenta("45678912", "Carmen Quispe Rojas", JUEGO_A, "912345678")  # juego A
        c002 = cuenta("87654321", "Pedro Huamán Salas", JUEGO_B, "923456789")  # juego B
        if c001.usuario_id is None:
            dar_acceso_cliente(c001, carmen.email, None, rosa)
        return c001, c002

    # -- operaciones de los juegos A y B (con los servicios reales) ------------------------
    def operaciones(self, rosa, tienda, articulo, c001, c002):
        def vender(cuenta, monto, fecha, modalidad="MENSUAL", n=None):
            return s.registrar_compra(rosa, tienda, cuenta.pk, [{"articulo_id": articulo.pk, "cantidad": str(monto)}],
                                      modalidad, n, fecha, uuid.uuid4())

        def pagar(cuenta, obligaciones, fecha, importe):
            return s.registrar_pago(rosa, tienda, cuenta.pk, [o.pk for o in obligaciones], fecha, importe, uuid.uuid4())

        # Juego A (TEA 24 %, fin de mes)
        vender(c001, 120, lima(2026, 9, 5, 10, 0))
        vender(c001, 80, lima(2026, 9, 18, 10, 0))
        vender(c001, 50, lima(2026, 9, 21, 10, 0))  # pasa al ciclo de octubre
        estado = s.generar_estado(c001, lima(2026, 9, 20, 20, 0), rosa)
        septiembre = list(c001.obligaciones.filter(vencimiento=date(2026, 9, 26)))
        pago_a = pagar(c001, septiembre, date(2026, 10, 1), "201.98")  # 5 días de atraso: mora 0.08

        # Juego B (TNA 24 % capitalización mensual, 3 cuotas)
        compra_b = vender(c002, 600, lima(2026, 9, 15, 10, 0), "CUOTAS", 3)
        pago_b = pagar(c002, [compra_b.obligaciones.get(numero=1)], date(2026, 10, 26), "209.57")

        generados = s.generar_estados_pendientes(tienda=tienda, usuario=rosa)
        self.stdout.write(self.style.SUCCESS(
            f"Juego A: estado {estado.total}, pago {pago_a.total}, disponible C001 {s.disponible(c001)}. "
            f"Juego B: Pg {compra_b.capital_con_gracia}, cuota {compra_b.cuota}, pago {pago_b.total}, "
            f"disponible C002 {s.disponible(c002)}. Estados adicionales: {len(generados)}."
        ))
