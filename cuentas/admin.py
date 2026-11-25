from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    """Usuarios en el registro central (/admin/), identificados por correo."""

    ordering = ["email"]
    list_display = ["email", "nombres", "apellidos", "is_staff", "is_active", "fecha_alta"]
    list_filter = ["is_staff", "is_active"]
    search_fields = ["email", "nombres", "apellidos"]
    readonly_fields = ["fecha_alta", "last_login"]
    fieldsets = [
        (None, {"fields": ["email", "password"]}),
        ("Datos personales", {"fields": ["nombres", "apellidos"]}),
        ("Permisos", {"fields": ["is_active", "is_staff", "is_superuser", "groups", "user_permissions"]}),
        ("Fechas", {"fields": ["fecha_alta", "last_login"]}),
    ]
    add_fieldsets = [
        (None, {"classes": ["wide"], "fields": ["email", "nombres", "password1", "password2"]}),
    ]
