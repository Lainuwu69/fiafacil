"""
Comando diario: genera los estados de cuenta de todos los cortes ya cumplidos.

Uso:
    python manage.py generar_estados

Se puede programar una vez al día (por ejemplo, con el Programador de tareas de
Windows a las 23:59). Es idempotente: si un estado ya existe, no lo duplica
(UNIQUE(cuenta, corte)).
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from creditos.servicios import generar_estados_pendientes


class Command(BaseCommand):
    help = "Genera los estados de cuenta de los cortes ya cumplidos que aún no tienen estado."

    def handle(self, *args, **opciones):
        estados = generar_estados_pendientes()
        for e in estados:
            self.stdout.write(
                f"  {e.cuenta.codigo} {e.cuenta.nombre}: corte {timezone.localtime(e.corte):%d/%m/%Y %H:%M}, "
                f"total {e.total} {e.cuenta.moneda}"
            )
        self.stdout.write(self.style.SUCCESS(f"Estados generados: {len(estados)}."))
