"""
Etiquetas y filtros de plantilla de FíaFácil.

    {% load ff %}
    {% campo form.tasa_valor %}      → campo con etiqueta, ícono ⓘ (tooltip) y ayuda debajo
    {{ monto|dinero:"PEN" }}        → S/ 1,250.50
    {{ tasa|tasa }}                  → 26.8241795 %   (al menos 7 decimales)
"""

from decimal import Decimal, InvalidOperation

from django import forms, template

from core.constantes import SIMBOLO_MONEDA
from creditos.finanzas import formato_tasa, r2

register = template.Library()


def _clase_widget(widget):
    if isinstance(widget, (forms.CheckboxInput, forms.RadioSelect, forms.CheckboxSelectMultiple)):
        return "form-check-input"
    if isinstance(widget, (forms.Select, forms.SelectMultiple)):
        return "form-select"
    return "form-control"


@register.inclusion_tag("parciales/campo.html")
def campo(bf, **atributos):
    """Dibuja un campo de formulario con su ayuda (rúbrica: ayuda en cada campo de la pantalla)."""
    widget = bf.field.widget
    # En plantillas no se puede escribir data-rol="x"; se escribe data_rol="x" y aquí se convierte.
    atributos = {(k.replace("_", "-") if k.startswith(("data_", "aria_")) else k): v for k, v in atributos.items()}
    clases = [_clase_widget(widget), atributos.pop("class", "")]
    if bf.errors:
        clases.append("is-invalid")
    attrs = {"class": " ".join(c for c in clases if c), **atributos}
    if bf.help_text:
        attrs["aria-describedby"] = f"ayuda_{bf.auto_id}"
    return {
        "bf": bf,
        "widget_html": bf.as_widget(attrs=attrs),
        "es_check": isinstance(widget, forms.CheckboxInput),
    }


@register.filter
def dinero(valor, moneda="PEN"):
    """Importe con símbolo, separador de miles y punto decimal: S/ 1,250.50."""
    if valor in (None, ""):
        return "—"
    try:
        monto = r2(Decimal(str(valor)))
    except (InvalidOperation, ValueError, TypeError):
        return valor
    simbolo = SIMBOLO_MONEDA.get(moneda, moneda or "")
    signo = "-" if monto < 0 else ""
    return f"{signo}{simbolo} {abs(monto):,.2f}".strip()


@register.filter
def tasa(valor, decimales=7):
    """Tasa decimal como porcentaje con al menos 7 decimales."""
    if valor in (None, ""):
        return "—"
    return formato_tasa(Decimal(str(valor)), int(decimales))


@register.filter
def porcentaje(valor, decimales=2):
    """Tasa decimal como porcentaje corto (para indicadores): 0.0563 → 5.63 %."""
    if valor in (None, ""):
        return "—"
    return formato_tasa(Decimal(str(valor)), int(decimales))
