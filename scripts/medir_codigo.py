"""
Mide el tamaño del código fuente de FíaFácil y estima el esfuerzo con COCOMO II.

Uso:  python scripts/medir_codigo.py

- Cuenta líneas de código (sin líneas en blanco ni comentarios de línea completa) por
  lenguaje, sin incluir librerías de terceros (static/vendor, .venv) ni migraciones
  generadas automáticamente (se informan aparte).
- COCOMO II, modelo Post-Architecture con todos los factores en su valor nominal
  (Boehm et al., 2000):
      E    = B + 0.01 × Σ SF          B = 0.91, Σ SF nominal = 18.97
      PM   = A × KSLOC^E × Π EM       A = 2.94, Π EM nominal = 1
      TDEV = C × PM^F                 C = 3.67, F = D + 0.2 × (E − B), D = 0.28
  PM = esfuerzo en personas-mes; TDEV = tiempo de desarrollo en meses.
  Es la estimación de un equipo humano promedio; sirve para comparar lo planificado con lo
  ejecutado (el proyecto se desarrolló con asistencia de IA, ver docs/REGISTRO_IA.md).
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
EXCLUIR = {".venv", "vendor", "media", "media_pruebas", "staticfiles", "__pycache__", "respaldos", ".claude"}
LENGUAJES = {".py": ("Python", "#"), ".js": ("JavaScript", "//"), ".html": ("HTML (plantillas Django)", None),
             ".css": ("CSS", None), ".ps1": ("PowerShell", "#")}


def contar(ruta, marca):
    n = 0
    en_bloque = False
    for linea in ruta.read_text(encoding="utf-8", errors="ignore").splitlines():
        t = linea.strip()
        if not t:
            continue
        if ruta.suffix == ".py" and (t.startswith('"""') or t.startswith("'''")):
            # docstrings de una línea o de varias: se cuentan como documentación, no como código
            if not (len(t) > 3 and t.endswith(t[:3]) and len(t) >= 6):
                en_bloque = not en_bloque
            continue
        if en_bloque:
            continue
        if marca and t.startswith(marca):
            continue
        n += 1
    return n


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    totales, migraciones, archivos = {}, 0, {}
    for ruta in RAIZ.rglob("*"):
        if not ruta.is_file() or ruta.suffix not in LENGUAJES or set(ruta.relative_to(RAIZ).parts) & EXCLUIR:
            continue
        nombre, marca = LENGUAJES[ruta.suffix]
        lineas = contar(ruta, marca)
        if "migrations" in ruta.parts:
            migraciones += lineas
            continue
        totales[nombre] = totales.get(nombre, 0) + lineas
        archivos[nombre] = archivos.get(nombre, 0) + 1
    total = sum(totales.values())
    print("Líneas de código (sin blancos ni comentarios; sin librerías de terceros):")
    for nombre, n in sorted(totales.items(), key=lambda x: -x[1]):
        print(f"  {nombre:<26} {n:>6}  ({archivos[nombre]} archivos)")
    print(f"  {'TOTAL':<26} {total:>6}")
    print(f"  (migraciones generadas por Django, no incluidas: {migraciones})")

    A, B, C, D, SF, EM = 2.94, 0.91, 3.67, 0.28, 18.97, 1.0
    ksloc = total / 1000
    E = B + 0.01 * SF
    pm = A * ksloc ** E * EM
    F = D + 0.2 * (E - B)
    tdev = C * pm ** F
    print("\nCOCOMO II (Post-Architecture, factores nominales):")
    print(f"  KSLOC = {ksloc:.3f}   E = {E:.4f}   F = {F:.4f}")
    print(f"  Esfuerzo PM   = 2.94 × {ksloc:.3f}^{E:.4f} = {pm:.2f} personas-mes")
    print(f"  Tiempo TDEV   = 3.67 × {pm:.2f}^{F:.4f} = {tdev:.2f} meses")
    print(f"  Personal promedio = PM / TDEV = {pm / tdev:.2f} personas")


if __name__ == "__main__":
    main()
