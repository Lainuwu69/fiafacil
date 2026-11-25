"""
Carga los topes de tasa compensatoria publicados por el BCRP (Circular N.º 0008-2021-BCRP).

Uso:
    python manage.py cargar_topes_bcrp

Fuentes (notas informativas oficiales del BCRP, Circular N.º 0008-2021-BCRP):
- Lima, 01/04/2026, periodo mayo–octubre 2026: «114,13 por ciento anual en moneda nacional y
  99,84 por ciento anual en moneda extranjera». Copia en docs/fuentes/.
- Lima, 01/10/2026, periodo noviembre 2026 – abril 2027: «114,68 por ciento anual en moneda
  nacional y 103,14 por ciento anual en moneda extranjera».
Se cargan los dos periodos porque las compras de los juegos A y B son de septiembre de 2026.

- Solo se cargan topes COMPENSATORIOS: la nota no fija la tasa moratoria.
- Las tasas se guardan en decimal (114.68 % = 1.1468) como tasa anual, comparable con la TEA pactada.
- Es idempotente: si el tope ya existe para esa moneda, tipo y vigencia, no lo duplica.
- Cada semestre (próxima actualización: 1 de mayo de 2027) se agrega aquí el nuevo periodo con su
  fuente oficial, o se carga en /admin/ (Topes de tasa). Nunca se usan cifras sin fuente oficial.
"""

from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand

from core.models import TopeTasa

NOTA_ABRIL = (
    "https://www.bcrp.gob.pe/docs/Transparencia/Notas-Informativas/2026/nota-informativa-2026-04-07.pdf",
    "Nota informativa BCRP del 01/04/2026: tasas máximas mayo 2026 – octubre 2026 (Circular N.º 0008-2021-BCRP).",
)
# La captura de la nota de octubre no mostraba la dirección del PDF: se registra la página oficial de notas.
NOTA_OCTUBRE = (
    "https://www.bcrp.gob.pe/transparencia/notas-informativas.html",
    "Nota informativa BCRP del 01/10/2026: tasas máximas noviembre 2026 – abril 2027 (Circular N.º 0008-2021-BCRP).",
)

TOPES = [
    # moneda, tipo, tasa anual en decimal, vigente desde, vigente hasta, (fuente, observación)
    ("PEN", TopeTasa.Tipo.COMPENSATORIA, Decimal("1.1413"), date(2026, 5, 1), date(2026, 10, 31), NOTA_ABRIL),
    ("USD", TopeTasa.Tipo.COMPENSATORIA, Decimal("0.9984"), date(2026, 5, 1), date(2026, 10, 31), NOTA_ABRIL),
    ("PEN", TopeTasa.Tipo.COMPENSATORIA, Decimal("1.1468"), date(2026, 11, 1), date(2027, 4, 30), NOTA_OCTUBRE),
    ("USD", TopeTasa.Tipo.COMPENSATORIA, Decimal("1.0314"), date(2026, 11, 1), date(2027, 4, 30), NOTA_OCTUBRE),
]


class Command(BaseCommand):
    help = "Carga los topes de tasa compensatoria vigentes publicados por el BCRP (con su fuente)."

    def handle(self, *args, **opciones):
        for moneda, tipo, valor, desde, hasta, (fuente, nota) in TOPES:
            tope, creado = TopeTasa.objects.get_or_create(
                moneda=moneda, tipo=tipo, vigente_desde=desde,
                defaults={"tasa_efectiva_anual": valor, "vigente_hasta": hasta, "fuente_url": fuente, "observacion": nota[:300]},
            )
            estado = "cargado" if creado else "ya existía"
            self.stdout.write(f"  {moneda} {tope.get_tipo_display()}: {tope.tasa_efectiva_anual * 100:.2f} % anual, "
                              f"{desde:%d/%m/%Y}–{hasta:%d/%m/%Y} ({estado})")
        self.stdout.write(self.style.SUCCESS("Topes del BCRP listos."))
