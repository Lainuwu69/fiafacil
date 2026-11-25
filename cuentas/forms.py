"""Formularios de registro e inicio de sesión. Cada campo lleva su ayuda (help_text) con ejemplo."""

import re
from datetime import timedelta

from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.utils import timezone

from core.models import Auditoria
from tiendas.models import Tienda

Usuario = get_user_model()

MAX_INTENTOS = 5
VENTANA_MINUTOS = 15


class RegistroForm(forms.Form):
    """Registro público: crea el usuario dueño y su tienda (queda PENDIENTE de activación)."""

    nombres = forms.CharField(label="Tus nombres", max_length=100, help_text="Como figuran en tu DNI. Ej.: Rosa María.")
    apellidos = forms.CharField(label="Tus apellidos", max_length=100, required=False, help_text="Opcional. Ej.: Quispe Torres.")
    email = forms.EmailField(
        label="Correo", max_length=254,
        help_text="Será tu usuario para iniciar sesión. Ej.: rosa@bodega.pe.",
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
    )
    password1 = forms.CharField(
        label="Contraseña", strip=False,
        help_text="Mínimo 8 caracteres; no uses solo números ni una clave común como 12345678.",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    password2 = forms.CharField(
        label="Repite la contraseña", strip=False, help_text="Escríbela otra vez para evitar errores de tipeo.",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    nombre_tienda = forms.CharField(label="Nombre de tu negocio", max_length=120, help_text=Tienda._meta.get_field("nombre").help_text)
    giro = forms.CharField(label="Giro", max_length=60, help_text=Tienda._meta.get_field("giro").help_text)
    ruc = forms.CharField(label="RUC", max_length=11, required=False, help_text=Tienda._meta.get_field("ruc").help_text)
    direccion = forms.CharField(label="Dirección del local", max_length=200, help_text=Tienda._meta.get_field("direccion").help_text)
    telefono = forms.CharField(label="Teléfono", max_length=20, required=False, help_text=Tienda._meta.get_field("telefono").help_text)
    acepta_privacidad = forms.BooleanField(
        label="Acepto el tratamiento de mis datos personales",
        help_text="Tus datos y los de tus clientes se usan solo para llevar las cuentas de tu negocio (Ley 29733).",
    )

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if Usuario.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Ya existe un usuario con ese correo. Inicia sesión o usa otro correo.")
        return email

    def clean_ruc(self):
        ruc = (self.cleaned_data.get("ruc") or "").strip()
        if ruc and not re.fullmatch(r"\d{11}", ruc):
            raise forms.ValidationError(f"El RUC debe tener 11 dígitos; escribiste {len(ruc)} caracteres.")
        return ruc or None

    def clean_telefono(self):
        telefono = (self.cleaned_data.get("telefono") or "").strip()
        if telefono and not re.fullmatch(r"[0-9 +()-]{6,20}", telefono):
            raise forms.ValidationError("Escribe solo números (puedes usar +, espacios o guiones). Ej.: 987654321.")
        return telefono

    def clean(self):
        datos = super().clean()
        p1, p2 = datos.get("password1"), datos.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Las contraseñas no coinciden.")
        if p1:
            temporal = Usuario(email=datos.get("email", ""), nombres=datos.get("nombres", ""), apellidos=datos.get("apellidos", ""))
            try:
                password_validation.validate_password(p1, temporal)
            except forms.ValidationError as e:
                self.add_error("password1", e)
        return datos


class CambioClaveForm(PasswordChangeForm):
    """Cambio de contraseña del propio usuario (pide la actual para confirmar que es él)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        ayudas = {
            "old_password": ("Contraseña actual", "La que usas hoy para entrar. Distingue mayúsculas y minúsculas."),
            "new_password1": ("Nueva contraseña", "Mínimo 8 caracteres; no uses solo números, tu correo ni claves comunes. Ej.: Bodega-Rosa-2026."),
            "new_password2": ("Repite la nueva contraseña", "Escríbela otra vez para evitar errores de tipeo."),
        }
        for nombre, (etiqueta, ayuda) in ayudas.items():
            self.fields[nombre].label = etiqueta
            self.fields[nombre].help_text = ayuda


class LoginForm(AuthenticationForm):
    """Inicio de sesión con correo y contraseña. Bloquea 15 minutos tras 5 intentos fallidos."""

    username = forms.EmailField(
        label="Correo", help_text="El correo con el que te registraste. Ej.: rosa@bodega.pe.",
        widget=forms.EmailInput(attrs={"autofocus": True, "autocomplete": "email"}),
    )
    password = forms.CharField(
        label="Contraseña", strip=False, help_text="Distingue mayúsculas y minúsculas.",
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )

    error_messages = {
        "invalid_login": "Correo o contraseña incorrectos. Revisa los datos e inténtalo otra vez.",
        "inactive": "Este usuario está desactivado. Comunícate con soporte.",
    }

    def clean(self):
        email = (self.cleaned_data.get("username") or "").strip().lower()
        if email:
            desde = timezone.now() - timedelta(minutes=VENTANA_MINUTOS)
            fallidos = Auditoria.objects.filter(
                evento=Auditoria.Evento.LOGIN_FALLIDO, instante__gte=desde, datos__email=email
            ).count()
            if fallidos >= MAX_INTENTOS:
                raise forms.ValidationError(
                    f"Demasiados intentos fallidos ({fallidos}). Por seguridad, espera {VENTANA_MINUTOS} minutos o escribe a soporte."
                )
            self.cleaned_data["username"] = email
        return super().clean()
