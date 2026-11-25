"""
Comportamientos comunes de los modelos.

RN09 (baja lógica) y RN10 (versiones): en FíaFácil nada financiero se borra
ni se reescribe. Las correcciones se hacen con registros nuevos.

- SinBorradoFisico: el registro puede editarse, pero no eliminarse; se da de
  baja marcándolo como inactivo (tiendas, artículos, clientes, membresías).
- RegistroInmutable: una vez guardado no se puede modificar ni eliminar,
  salvo los campos que el modelo declare en `campos_actualizables` (por
  ejemplo, el estado de una obligación al pagarse).
"""

from django.db import models


class OperacionNoPermitida(Exception):
    """Se intentó borrar o modificar un registro que debe conservarse."""


class SinBorradoFisico(models.Model):
    class Meta:
        abstract = True

    def delete(self, *args, **kwargs):
        raise OperacionNoPermitida(
            f"No se puede eliminar {self._meta.verbose_name} «{self}»: "
            "se da de baja marcándolo como inactivo y se conserva su historial (RN09)."
        )


class RegistroInmutable(models.Model):
    # Campos que sí pueden cambiar después de creado el registro.
    campos_actualizables: tuple = ()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            campos = kwargs.get("update_fields")
            if not campos or not set(campos) <= set(self.campos_actualizables):
                permitidos = ", ".join(self.campos_actualizables) or "ninguno"
                raise OperacionNoPermitida(
                    f"{self._meta.verbose_name.capitalize()} ya registrado no se puede modificar "
                    f"(campos actualizables: {permitidos}). Registre una corrección nueva (RN09, RN10)."
                )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise OperacionNoPermitida(
            f"No se puede eliminar {self._meta.verbose_name}: los registros financieros se conservan (RN09)."
        )


def siguiente_numero(queryset, campo="numero"):
    """Devuelve el siguiente correlativo (max + 1) dentro del queryset dado.

    Debe llamarse dentro de una transacción que bloquee a la tienda o cuenta
    (select_for_update); la restricción UNIQUE de la tabla es la última defensa.
    """
    ultimo = queryset.aggregate(m=models.Max(campo))["m"]
    return (ultimo or 0) + 1
