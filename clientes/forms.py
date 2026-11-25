"""Formularios de clientes: datos generales, condiciones de crédito (tasas en %) y acceso al portal."""

from datetime import time
from decimal import Decimal

from django import forms
from django.contrib.auth import password_validation
from django.utils import timezone

from clientes.models import CondicionCredito, CuentaCliente
from core.constantes import PeriodoTasa, TipoTasa

CIEN = Decimal("100")
_c = CondicionCredito._meta.get_field


class CuentaForm(forms.ModelForm):
    class Meta:
        model = CuentaCliente
        fields = ["tipo_documento", "documento", "nombre", "telefono", "correo", "direccion", "moneda"]

    def __init__(self, *args, tienda=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tienda = tienda
        if self.instance.pk:
            # RN02: la moneda de una cuenta no cambia (para otra moneda se abre otra cuenta).
            self.fields["moneda"].disabled = True

    def clean_documento(self):
        doc = self.cleaned_data["documento"].strip().upper()
        tipo = self.cleaned_data.get("tipo_documento")
        if tipo == "DNI" and not (doc.isdigit() and len(doc) == 8):
            raise forms.ValidationError(f"El DNI tiene 8 dígitos; escribiste {len(doc)} caracteres.")
        if tipo == "RUC" and not (doc.isdigit() and len(doc) == 11):
            raise forms.ValidationError("El RUC tiene 11 dígitos.")
        return doc

    def clean(self):
        datos = super().clean()
        doc, moneda = datos.get("documento"), datos.get("moneda") or self.instance.moneda
        if doc and self.tienda:
            repetida = CuentaCliente.objects.filter(tienda=self.tienda, documento=doc, moneda=moneda).exclude(pk=self.instance.pk)
            if repetida.exists():
                raise forms.ValidationError(f"Ya existe la cuenta {repetida.first().codigo} con ese documento en {moneda}.")
        return datos


class CondicionForm(forms.Form):
    """Condiciones pactadas. Las tasas se escriben en PORCENTAJE (24 = 24 %) y se guardan en decimal (0.24)."""

    tasa_tipo = forms.ChoiceField(label="Tipo de tasa", choices=TipoTasa.choices, help_text=_c("tasa_tipo").help_text)
    tasa_porcentaje = forms.DecimalField(
        label="Tasa compensatoria (%)", min_value=Decimal("0"), max_digits=12, decimal_places=7,
        help_text="Escribe el porcentaje con punto decimal: 24 para 24 %; 2.5 para 2.5 %.",
        widget=forms.NumberInput(attrs={"step": "any", "inputmode": "decimal"}),
    )
    tasa_periodo = forms.TypedChoiceField(label="Periodo de la tasa", coerce=int, choices=PeriodoTasa.choices,
                                          initial=PeriodoTasa.ANUAL, help_text=_c("tasa_periodo").help_text)
    tasa_capitalizacion = forms.TypedChoiceField(
        label="Capitalización", coerce=int, empty_value=None, required=False,
        choices=[("", "— (diaria si es nominal)")] + list(PeriodoTasa.choices), help_text=_c("tasa_capitalizacion").help_text,
    )
    mora_tipo = forms.ChoiceField(label="Tipo de tasa moratoria", choices=TipoTasa.choices, help_text=_c("mora_tipo").help_text)
    mora_porcentaje = forms.DecimalField(
        label="Tasa moratoria (%)", min_value=Decimal("0"), max_digits=12, decimal_places=7,
        help_text="Porcentaje que se cobra por los días de atraso. Ej.: 3 para 3 %.",
        widget=forms.NumberInput(attrs={"step": "any", "inputmode": "decimal"}),
    )
    mora_periodo = forms.TypedChoiceField(label="Periodo de la tasa moratoria", coerce=int, choices=PeriodoTasa.choices,
                                          initial=PeriodoTasa.ANUAL, help_text=_c("mora_periodo").help_text)
    mora_capitalizacion = forms.TypedChoiceField(
        label="Capitalización moratoria", coerce=int, empty_value=None, required=False,
        choices=[("", "— (diaria si es nominal)")] + list(PeriodoTasa.choices), help_text=_c("mora_capitalizacion").help_text,
    )
    limite = forms.DecimalField(label="Límite de crédito", min_value=Decimal("0.01"), max_digits=18, decimal_places=2,
                                help_text=_c("limite").help_text, widget=forms.NumberInput(attrs={"step": "0.01", "inputmode": "decimal"}))
    plazo_max = forms.IntegerField(label="Máximo de cuotas", min_value=1, max_value=60, initial=3, help_text=_c("plazo_max").help_text)
    dia_corte = forms.IntegerField(label="Día de corte", min_value=1, max_value=27, initial=20, help_text=_c("dia_corte").help_text)
    hora_corte = forms.TimeField(label="Hora de corte", initial=time(20, 0), help_text=_c("hora_corte").help_text,
                                 widget=forms.TimeInput(attrs={"type": "time", "step": "1"}, format="%H:%M:%S"))
    dia_pago = forms.IntegerField(label="Día de pago", min_value=2, max_value=28, initial=26, help_text=_c("dia_pago").help_text)
    vigente_desde = forms.DateTimeField(
        label="Vigente desde", required=False,
        help_text="Desde cuándo rigen. Déjalo vacío para hoy. Para pasar fiados antiguos del cuaderno, usa una fecha anterior a esas compras.",
        widget=forms.DateTimeInput(attrs={"type": "datetime-local", "step": "1"}, format="%Y-%m-%dT%H:%M:%S"),
    )

    def clean_vigente_desde(self):
        valor = self.cleaned_data.get("vigente_desde")
        if valor and valor > timezone.now():
            raise forms.ValidationError("No puede ser una fecha futura.")
        return valor

    def clean(self):
        datos = super().clean()
        corte, pago = datos.get("dia_corte"), datos.get("dia_pago")
        if corte and pago and pago <= corte:
            self.add_error("dia_pago", f"El día de pago ({pago}) debe ser posterior al día de corte ({corte}) (RN04).")
        for prefijo in ("tasa", "mora"):
            tipo, periodo, cap = datos.get(f"{prefijo}_tipo"), datos.get(f"{prefijo}_periodo"), datos.get(f"{prefijo}_capitalizacion")
            if tipo == TipoTasa.NOMINAL and cap and periodo and (cap > periodo or periodo % cap):
                self.add_error(f"{prefijo}_capitalizacion", f"Debe dividir exactamente al periodo ({periodo} días); por ejemplo, 30 para una TNA mensual.")
        return datos

    def a_datos(self):
        """Convierte a los campos del modelo: porcentajes → decimal."""
        d = self.cleaned_data
        return {
            "tasa_tipo": d["tasa_tipo"], "tasa_valor": d["tasa_porcentaje"] / CIEN, "tasa_periodo": d["tasa_periodo"],
            "tasa_capitalizacion": d.get("tasa_capitalizacion"),
            "mora_tipo": d["mora_tipo"], "mora_valor": d["mora_porcentaje"] / CIEN, "mora_periodo": d["mora_periodo"],
            "mora_capitalizacion": d.get("mora_capitalizacion"),
            "limite": d["limite"], "plazo_max": d["plazo_max"], "dia_corte": d["dia_corte"],
            "hora_corte": d["hora_corte"], "dia_pago": d["dia_pago"],
        }

    @classmethod
    def desde_condicion(cls, c):
        """Valores iniciales a partir de una versión existente (para proponer el cambio)."""
        return {
            "tasa_tipo": c.tasa_tipo, "tasa_porcentaje": (c.tasa_valor * CIEN).normalize(), "tasa_periodo": c.tasa_periodo,
            "tasa_capitalizacion": c.tasa_capitalizacion, "mora_tipo": c.mora_tipo, "mora_porcentaje": (c.mora_valor * CIEN).normalize(),
            "mora_periodo": c.mora_periodo, "mora_capitalizacion": c.mora_capitalizacion, "limite": c.limite,
            "plazo_max": c.plazo_max, "dia_corte": c.dia_corte, "hora_corte": c.hora_corte, "dia_pago": c.dia_pago,
        }


class AccesoForm(forms.Form):
    email = forms.EmailField(label="Correo del cliente", help_text="Con este correo el cliente entrará al portal. Ej.: carmen@cliente.pe.")
    password = forms.CharField(
        label="Contraseña inicial", required=False, strip=False,
        help_text="Solo si el correo aún no tiene usuario. Mínimo 8 caracteres; entrégasela al cliente en persona.",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    def clean_password(self):
        clave = self.cleaned_data.get("password")
        if clave:
            password_validation.validate_password(clave)
        return clave
