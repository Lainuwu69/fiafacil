"""
Registro central (/admin/) para el administrador de la plataforma.

- Las tablas financieras (compras, obligaciones, estados, pagos) y la auditoría son de
  SOLO LECTURA: nada financiero se edita ni se borra (RN09, RN10). Sirven para consultar
  y para mostrar en la exposición que todo el proceso quedó registrado.
- Tiendas, artículos, clientes y condiciones también se muestran solo para consulta:
  se administran desde las pantallas del sistema, que validan las reglas de negocio.
- TopeTasa sí se puede cargar aquí, siempre con la URL de la publicación oficial del BCRP.
"""

from django.contrib import admin

from clientes.models import CondicionCredito, CuentaCliente
from core.models import Auditoria, TopeTasa
from creditos.models import Anulacion, Compra, DetalleCompra, EstadoCuenta, EstadoDetalle, Obligacion, Pago, PagoAplicacion
from cuentas.models import Membresia
from tiendas.models import Articulo, Tienda


class SoloLectura(admin.ModelAdmin):
    """Permite ver y buscar, pero no agregar, modificar ni borrar."""

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class DetalleCompraInline(admin.TabularInline):
    model = DetalleCompra
    extra = 0
    can_delete = False
    readonly_fields = ["linea", "articulo", "descripcion", "unidad", "cantidad", "precio_unitario", "precio_contado", "importe"]

    def has_add_permission(self, request, obj=None):
        return False


class ObligacionInline(DetalleCompraInline):
    model = Obligacion
    readonly_fields = ["numero", "tipo", "vencimiento", "saldo_inicial", "capital", "interes", "total", "saldo_final", "estado", "pagada_en"]


class EstadoDetalleInline(DetalleCompraInline):
    model = EstadoDetalle
    readonly_fields = ["orden", "fecha_compra", "descripcion", "dias", "capital", "interes", "total"]


class PagoAplicacionInline(DetalleCompraInline):
    model = PagoAplicacion
    readonly_fields = ["obligacion", "dias_mora", "mora", "interes", "capital", "total"]


@admin.register(Tienda)
class TiendaAdmin(SoloLectura):
    list_display = ["codigo", "nombre", "giro", "estado", "fecha_alta", "fecha_activacion"]
    list_filter = ["estado", "giro"]
    search_fields = ["codigo", "nombre", "ruc"]


@admin.register(Membresia)
class MembresiaAdmin(SoloLectura):
    list_display = ["usuario", "tienda", "rol", "activo", "fecha_alta"]
    list_filter = ["rol", "activo"]


@admin.register(Articulo)
class ArticuloAdmin(SoloLectura):
    list_display = ["descripcion", "tienda", "unidad", "precio_contado", "precio_credito", "permite_mensual", "permite_cuotas", "activo"]
    list_filter = ["tienda", "activo"]
    search_fields = ["descripcion", "marca"]


@admin.register(CuentaCliente)
class CuentaClienteAdmin(SoloLectura):
    list_display = ["codigo", "nombre", "tienda", "documento", "moneda", "usuario", "activo"]
    list_filter = ["tienda", "moneda", "activo"]
    search_fields = ["codigo", "nombre", "documento"]


@admin.register(CondicionCredito)
class CondicionCreditoAdmin(SoloLectura):
    list_display = ["cuenta", "version", "tasa_tipo", "tasa_valor", "limite", "dia_corte", "dia_pago", "vigente_desde", "vigente_hasta"]
    list_filter = ["tasa_tipo"]


@admin.register(Compra)
class CompraAdmin(SoloLectura):
    list_display = ["numero", "tienda", "cuenta", "fecha_compra", "modalidad", "n_cuotas", "capital", "interes", "total", "tcea"]
    list_filter = ["tienda", "modalidad"]
    date_hierarchy = "fecha_compra"
    inlines = [DetalleCompraInline, ObligacionInline]


@admin.register(Obligacion)
class ObligacionAdmin(SoloLectura):
    list_display = ["compra", "numero", "tipo", "cuenta", "vencimiento", "capital", "interes", "total", "estado"]
    list_filter = ["estado", "tipo", "tienda"]


@admin.register(EstadoCuenta)
class EstadoCuentaAdmin(SoloLectura):
    list_display = ["cuenta", "corte", "fecha_pago", "capital", "interes", "total", "generado_en"]
    list_filter = ["tienda"]
    inlines = [EstadoDetalleInline]


@admin.register(Pago)
class PagoAdmin(SoloLectura):
    list_display = ["numero", "tienda", "cuenta", "fecha_efectiva", "mora", "interes", "capital", "total", "registrado_por"]
    list_filter = ["tienda"]
    inlines = [PagoAplicacionInline]


@admin.register(Anulacion)
class AnulacionAdmin(SoloLectura):
    list_display = ["registrada_en", "tienda", "tipo", "compra", "pago", "motivo", "registrada_por"]
    list_filter = ["tipo", "tienda"]


@admin.register(Auditoria)
class AuditoriaAdmin(SoloLectura):
    list_display = ["instante", "evento", "usuario", "tienda", "descripcion", "ip"]
    list_filter = ["evento", "tienda"]
    search_fields = ["descripcion", "usuario__email"]
    date_hierarchy = "instante"


@admin.register(TopeTasa)
class TopeTasaAdmin(admin.ModelAdmin):
    """Topes del BCRP (Circular 0008-2021-BCRP). Cárguelos solo desde la publicación oficial."""

    list_display = ["moneda", "tipo", "tasa_efectiva_anual", "vigente_desde", "vigente_hasta", "fuente_url"]
    list_filter = ["moneda", "tipo"]
