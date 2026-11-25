"""
Formatos de fecha y número para Perú (es-PE).

Django trae formatos para el español genérico con coma decimal; en Perú se usa
punto decimal (S/ 1,250.50) y fechas día/mes/año. Este módulo los reemplaza.
Los códigos siguen la sintaxis de Django (d=día, m=mes, Y=año, H=hora, i=minutos).
"""

# Cómo se muestran las fechas en las plantillas
DATE_FORMAT = "d/m/Y"
SHORT_DATE_FORMAT = "d/m/Y"
DATETIME_FORMAT = "d/m/Y H:i"
SHORT_DATETIME_FORMAT = "d/m/Y H:i"
TIME_FORMAT = "H:i"
MONTH_DAY_FORMAT = "j \\d\\e F"
YEAR_MONTH_FORMAT = "F \\d\\e Y"
FIRST_DAY_OF_WEEK = 1  # lunes

# Cómo se aceptan las fechas escritas en los formularios (el primero es el preferido).
# También se acepta el formato ISO, que es el que envían los campos <input type="date">.
DATE_INPUT_FORMATS = [
    "%d/%m/%Y",  # 15/09/2026
    "%Y-%m-%d",  # 2026-09-15
]
DATETIME_INPUT_FORMATS = [
    "%d/%m/%Y %H:%M:%S",  # 15/09/2026 19:59:59
    "%d/%m/%Y %H:%M",  # 15/09/2026 19:59
    "%Y-%m-%dT%H:%M:%S",  # formato de <input type="datetime-local">
    "%Y-%m-%dT%H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
]

# Números: punto decimal y coma para los miles
DECIMAL_SEPARATOR = "."
THOUSAND_SEPARATOR = ","
NUMBER_GROUPING = 3
