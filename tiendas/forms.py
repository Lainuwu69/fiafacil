"""Formulario del catálogo: producto o servicio con imagen obligatoria (máximo 2 MB)."""

from django import forms
from django.conf import settings

from tiendas.models import Articulo

FORMATOS_IMAGEN = {"JPEG", "PNG", "WEBP"}


class ArticuloForm(forms.ModelForm):
    class Meta:
        model = Articulo
        fields = ["descripcion", "proveedor", "marca", "unidad", "imagen", "precio_contado", "precio_credito",
                  "permite_mensual", "permite_cuotas"]
        widgets = {
            "imagen": forms.ClearableFileInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
            "precio_contado": forms.NumberInput(attrs={"step": "0.01", "min": "0.01", "inputmode": "decimal"}),
            "precio_credito": forms.NumberInput(attrs={"step": "0.01", "min": "0.01", "inputmode": "decimal"}),
        }

    def clean_imagen(self):
        imagen = self.cleaned_data.get("imagen")
        if not imagen:
            raise forms.ValidationError("La imagen es obligatoria (RN11).")
        if hasattr(imagen, "size") and getattr(imagen, "content_type", None) is not None:  # archivo recién subido
            if imagen.size > settings.IMAGEN_MAX_BYTES:
                raise forms.ValidationError(
                    f"La imagen pesa {imagen.size / 1024 / 1024:.2f} MB; el máximo es {settings.IMAGEN_MAX_BYTES / 1024 / 1024:.0f} MB."
                )
            formato = getattr(getattr(imagen, "image", None), "format", None)
            if formato and formato.upper() not in FORMATOS_IMAGEN:
                raise forms.ValidationError(f"Formato {formato} no permitido; usa JPG, PNG o WEBP.")
        return imagen

    def clean(self):
        datos = super().clean()
        if not datos.get("permite_mensual") and not datos.get("permite_cuotas"):
            raise forms.ValidationError("Marca al menos una forma de venta: a fin de mes o en cuotas (RN11).")
        contado, credito = datos.get("precio_contado"), datos.get("precio_credito")
        if contado and credito and credito < contado:
            self.add_error("precio_credito", f"El precio de lista ({credito}) no debería ser menor que el precio contado ({contado}).")
        return datos
