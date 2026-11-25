"""
MODELO MATEMÁTICO DE FÍAFÁCIL (capítulo 3 del informe del Hito 1).

Este módulo es "puro": no usa la base de datos ni Django. Recibe números y
fechas, y devuelve resultados. Por eso se puede probar contra los juegos A y B
del informe sin nada más.

Convenciones del curso (Anexo A del enunciado, sección 3.3.1 del informe):
- Año de 360 días y mes comercial de 30 días.
- Días exactos entre fechas: se excluye el primer día y se incluye el último.
- Tasa nominal sin capitalización indicada → capitalización diaria (1 día).
- Tasa sin periodo indicado → anual (360 días).
- Importes redondeados a 2 decimales con HALF_UP (RN12); tasas con 40 dígitos
  de precisión interna y mostradas con al menos 7 decimales.
- Siempre Decimal, nunca float.

Fórmulas (capítulo 3):
    Tasa efectiva para d días:   i(d) = (1 + i(p))^(d/p) − 1
    Tasa nominal para d días:    m = p/c ; i(d) = (1 + j/m)^(d/c) − 1
    Compra mensual:              I = R2(P × i(D(compra, vencimiento))) ; V = P + I
    Mora:                        M = R2(V × iₘ(dₘ)), dₘ = max(0, D(vencimiento, pago))
    Gracia total:                Pg = R2(P × (1 + TEM)^(g/30))
    Cuota francesa:              C = R2(Pg × i / [1 − (1 + i)^(−n)]) ; si i = 0, C = Pg / n
    Componentes de cada cuota:   Iₖ = R2(Sₖ₋₁ × i) ; Aₖ = C − Iₖ ; Sₖ = Sₖ₋₁ − Aₖ (última ajustada)
    Crédito disponible:          Disponible = Límite − Exposición
    TCEA (ajuste A):             Σ Fₜ / (1 + TCEA)^(tₜ/360) = Valor recibido
"""

import calendar
from dataclasses import dataclass, field
from datetime import date, datetime, time
from decimal import ROUND_HALF_UP, Context, Decimal, localcontext
from functools import wraps
from zoneinfo import ZoneInfo

ZONA_LIMA = ZoneInfo("America/Lima")
DIAS_ANIO = 360
DIAS_MES = 30
CERO = Decimal("0")
UNO = Decimal("1")
CENTIMO = Decimal("0.01")

# Contexto de alta precisión: 40 dígitos significativos para tasas y potencias.
CONTEXTO = Context(prec=40)


class ErrorFinanciero(ValueError):
    """Dato que hace imposible o inválido un cálculo (mensaje en español para el usuario)."""


def _preciso(funcion):
    """Ejecuta la función con 40 dígitos de precisión decimal."""

    @wraps(funcion)
    def envoltura(*args, **kwargs):
        with localcontext(CONTEXTO):
            return funcion(*args, **kwargs)

    return envoltura


def D(valor):
    """Convierte a Decimal sin pasar por float (str primero). Rechaza float."""
    if isinstance(valor, Decimal):
        return valor
    if isinstance(valor, float):
        raise TypeError("No se aceptan float en cálculos financieros; use Decimal o str.")
    return Decimal(str(valor))


def r2(valor):
    """Redondeo monetario a 2 decimales con HALF_UP (RN12): 2.675 → 2.68; 0.125 → 0.13."""
    return D(valor).quantize(CENTIMO, rounding=ROUND_HALF_UP)


def formato_tasa(valor, decimales=7):
    """Muestra una tasa decimal como porcentaje con al menos 7 decimales: 0.24 → '24.0000000 %'."""
    porcentaje = D(valor) * 100
    return f"{porcentaje.quantize(Decimal(1).scaleb(-decimales), rounding=ROUND_HALF_UP)} %"


# ---------------------------------------------------------------------------
# Fechas
# ---------------------------------------------------------------------------

def a_fecha_lima(valor):
    """Convierte un datetime con zona a su fecha en Lima; una date se devuelve igual."""
    if isinstance(valor, datetime):
        if valor.tzinfo is None:
            raise ErrorFinanciero("La fecha y hora debe indicar su zona horaria.")
        return valor.astimezone(ZONA_LIMA).date()
    return valor


def dias_exactos(desde, hasta):
    """D(F₁, F₂): días calendario entre dos fechas, sin contar el primero y contando el último.

    Ej.: del 26/09 al 01/10 hay 5 días. Rechaza intervalos invertidos.
    """
    f1, f2 = a_fecha_lima(desde), a_fecha_lima(hasta)
    if f2 < f1:
        raise ErrorFinanciero(f"Intervalo invertido: {f2:%d/%m/%Y} es anterior a {f1:%d/%m/%Y}.")
    return (f2 - f1).days


def sumar_meses(fecha, meses):
    """Misma fecha k meses después (el día de pago está entre 2 y 28, así que siempre existe)."""
    total = fecha.month - 1 + meses
    anio, mes = fecha.year + total // 12, total % 12 + 1
    dia = min(fecha.day, calendar.monthrange(anio, mes)[1])
    return date(anio, mes, dia)


@dataclass(frozen=True)
class Ciclo:
    corte: datetime  # fecha y hora del corte (zona Lima)
    fecha_pago: date  # fecha de pago del ciclo (vencimiento mensual o fin de gracia G)


def ciclo_de_compra(fecha_hora, dia_corte, hora_corte, dia_pago):
    """RN03: el ciclo de una compra es el del primer corte ESTRICTAMENTE posterior.

    Compra antes del corte del mes → ciclo de ese mes. Compra a la hora exacta del
    corte o después → ciclo del mes siguiente. La comparación se hace en hora de Lima.
    """
    if not 1 <= dia_corte <= 27 or not 2 <= dia_pago <= 28 or dia_pago <= dia_corte:
        raise ErrorFinanciero("Calendario inválido: corte 1–27, pago 2–28 y pago posterior al corte (RN04).")
    if not isinstance(fecha_hora, datetime) or fecha_hora.tzinfo is None:
        raise ErrorFinanciero("La fecha de compra debe ser fecha y hora con zona horaria.")
    if not isinstance(hora_corte, time):
        raise ErrorFinanciero("La hora de corte debe ser una hora (HH:MM).")
    local = fecha_hora.astimezone(ZONA_LIMA)
    corte = datetime.combine(date(local.year, local.month, dia_corte), hora_corte, tzinfo=ZONA_LIMA)
    if local >= corte:
        siguiente = sumar_meses(corte.date(), 1)
        corte = datetime.combine(siguiente, hora_corte, tzinfo=ZONA_LIMA)
    return Ciclo(corte=corte, fecha_pago=date(corte.year, corte.month, dia_pago))


# ---------------------------------------------------------------------------
# Tasas
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Tasa:
    """Tasa pactada: tipo NOMINAL o EFECTIVA, valor decimal (0.24 = 24 %), periodo y capitalización en días."""

    tipo: str
    valor: Decimal
    periodo: int = DIAS_ANIO
    capitalizacion: int | None = None

    def __post_init__(self):
        object.__setattr__(self, "valor", D(self.valor))
        tipo = (self.tipo or "").upper()
        if tipo not in ("NOMINAL", "EFECTIVA"):
            raise ErrorFinanciero("El tipo de tasa debe ser NOMINAL o EFECTIVA.")
        object.__setattr__(self, "tipo", tipo)
        if not self.periodo:
            object.__setattr__(self, "periodo", DIAS_ANIO)  # sin periodo → anual
        if tipo == "NOMINAL" and not self.capitalizacion:
            object.__setattr__(self, "capitalizacion", 1)  # nominal sin capitalización → diaria
        if tipo == "EFECTIVA":
            object.__setattr__(self, "capitalizacion", None)
        if self.valor < 0:
            raise ErrorFinanciero("La tasa no puede ser negativa.")
        if self.periodo <= 0:
            raise ErrorFinanciero("El periodo de la tasa debe ser mayor que cero.")
        if tipo == "NOMINAL" and (self.capitalizacion > self.periodo or self.periodo % self.capitalizacion):
            raise ErrorFinanciero(
                f"La capitalización ({self.capitalizacion} días) debe dividir exactamente al periodo ({self.periodo} días)."
            )

    @_preciso
    def efectiva(self, dias):
        """i(d): tasa efectiva equivalente para d días."""
        d = D(dias)
        if d < 0:
            raise ErrorFinanciero("Los días no pueden ser negativos.")
        if self.tipo == "EFECTIVA":
            return (UNO + self.valor) ** (d / D(self.periodo)) - UNO
        m = D(self.periodo) / D(self.capitalizacion)
        return (UNO + self.valor / m) ** (d / D(self.capitalizacion)) - UNO

    def tem(self):
        """Tasa efectiva mensual (30 días)."""
        return self.efectiva(DIAS_MES)

    def tea(self):
        """Tasa efectiva anual (360 días)."""
        return self.efectiva(DIAS_ANIO)


# ---------------------------------------------------------------------------
# Compra a fin de mes (pago único)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ResultadoMensual:
    dias: int
    tasa_periodo: Decimal  # i(días)
    capital: Decimal
    interes: Decimal
    total: Decimal


@_preciso
def compra_mensual(capital, tasa, fecha_compra, fecha_pago):
    """I = R2(P × i(D(compra, vencimiento))); V = P + I."""
    P = r2(capital)
    if P <= 0:
        raise ErrorFinanciero("El capital de la compra debe ser mayor que cero.")
    dias = dias_exactos(fecha_compra, fecha_pago)
    i_d = tasa.efectiva(dias)
    interes = r2(P * i_d)
    return ResultadoMensual(dias=dias, tasa_periodo=i_d, capital=P, interes=interes, total=P + interes)


# ---------------------------------------------------------------------------
# Compra en cuotas: gracia total + método francés vencido
# ---------------------------------------------------------------------------

@_preciso
def capital_con_gracia(capital, tem, dias_gracia):
    """Pg = R2(P × (1 + TEM)^(g/30)): los intereses de la gracia se capitalizan."""
    if dias_gracia < 0:
        raise ErrorFinanciero("Los días de gracia no pueden ser negativos.")
    return r2(D(capital) * (UNO + D(tem)) ** (D(dias_gracia) / D(DIAS_MES)))


@_preciso
def cuota_francesa(capital, i, n):
    """C = R2(Pg × i / [1 − (1 + i)^(−n)]); si i = 0, C = R2(Pg / n)."""
    Pg, i = D(capital), D(i)
    if Pg <= 0:
        raise ErrorFinanciero("El capital a financiar debe ser mayor que cero.")
    if n < 1:
        raise ErrorFinanciero("El número de cuotas debe ser al menos 1.")
    if i == 0:
        return r2(Pg / n)
    return r2(Pg * i / (UNO - (UNO + i) ** (-n)))


@dataclass(frozen=True)
class FilaCronograma:
    numero: int
    vencimiento: date
    saldo_inicial: Decimal
    interes: Decimal
    cuota: Decimal
    amortizacion: Decimal
    saldo_final: Decimal


@_preciso
def cronograma_frances(capital, i, n, fin_gracia):
    """Cronograma de n cuotas. La cuota k vence k meses después de G (fin de gracia).

    Iₖ = R2(Sₖ₋₁ × i); Aₖ = C − Iₖ; Sₖ = Sₖ₋₁ − Aₖ. En la última cuota
    Cₙ = Sₙ₋₁ + Iₙ, de modo que el saldo final es exactamente 0.00.
    """
    Pg, i = r2(capital), D(i)
    C = cuota_francesa(Pg, i, n)
    saldo = Pg
    filas = []
    for k in range(1, n + 1):
        interes = r2(saldo * i)
        cuota = r2(saldo + interes) if k == n else C
        amortizacion = cuota - interes
        nuevo_saldo = saldo - amortizacion
        if amortizacion <= 0 or nuevo_saldo < 0:
            raise ErrorFinanciero(
                f"El monto es demasiado pequeño para {n} cuotas (la cuota {k} no amortiza capital). Reduzca el número de cuotas."
            )
        filas.append(FilaCronograma(k, sumar_meses(fin_gracia, k), saldo, interes, cuota, amortizacion, nuevo_saldo))
        saldo = nuevo_saldo
    if saldo != 0:
        raise ErrorFinanciero("El cronograma no cerró en 0.00.")  # salvaguarda; no debería ocurrir
    return filas


@dataclass(frozen=True)
class ResultadoCuotas:
    capital: Decimal
    dias_gracia: int
    tem: Decimal
    capital_con_gracia: Decimal
    interes_gracia: Decimal
    cuota: Decimal
    filas: list = field(default_factory=list)

    @property
    def interes_cuotas(self):
        return sum((f.interes for f in self.filas), CERO)

    @property
    def total_pagado(self):
        return sum((f.cuota for f in self.filas), CERO)

    @property
    def interes_total(self):
        """Costo financiero sobre el capital original: gracia + intereses de las cuotas."""
        return self.total_pagado - self.capital


@_preciso
def compra_en_cuotas(capital, tasa, fecha_compra, fin_gracia, n):
    """Gracia total desde la compra hasta G y cronograma francés de n cuotas (RN05)."""
    P = r2(capital)
    if P <= 0:
        raise ErrorFinanciero("El capital de la compra debe ser mayor que cero.")
    g = dias_exactos(fecha_compra, fin_gracia)
    tem = tasa.tem()
    Pg = capital_con_gracia(P, tem, g)
    filas = cronograma_frances(Pg, tem, n, fin_gracia)
    return ResultadoCuotas(
        capital=P, dias_gracia=g, tem=tem, capital_con_gracia=Pg, interes_gracia=Pg - P, cuota=filas[0].cuota, filas=filas
    )


# ---------------------------------------------------------------------------
# Mora
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ResultadoMora:
    dias: int
    tasa: Decimal
    mora: Decimal


@_preciso
def calcular_mora(base, tasa_mora, vencimiento, fecha_pago):
    """M = R2(V × iₘ(dₘ)) con dₘ = max(0, D(vencimiento, pago)). Sin mora sobre mora (RN08)."""
    venc, pago = a_fecha_lima(vencimiento), a_fecha_lima(fecha_pago)
    dias = 0 if pago <= venc else dias_exactos(venc, pago)
    i_m = tasa_mora.efectiva(dias) if dias else CERO
    return ResultadoMora(dias=dias, tasa=i_m, mora=r2(D(base) * i_m))


# ---------------------------------------------------------------------------
# Crédito disponible (RN06)
# ---------------------------------------------------------------------------

def disponible(limite, exposicion):
    """Disponible = Límite − Exposición (la exposición no incluye intereses futuros)."""
    return r2(D(limite) - D(exposicion))


def cabe_en_limite(limite, exposicion, nuevo_capital):
    """E + nuevo ≤ L. En cuotas, el nuevo capital es Pg (gracia capitalizada)."""
    return r2(D(exposicion) + D(nuevo_capital)) <= r2(limite)


# ---------------------------------------------------------------------------
# TCEA: costo efectivo anual (ajuste A, rúbrica del logro del curso)
# ---------------------------------------------------------------------------

@_preciso
def tcea(valor_recibido, flujos):
    """Tasa de costo efectivo anual: la TIR de los flujos, expresada en un año de 360 días.

    Resuelve  Σ Fₜ / (1 + TCEA)^(tₜ/360) = valor recibido.
    `flujos` es una lista de (días desde la compra, importe que paga el cliente). Los días
    siguen la misma convención del cálculo: días exactos hasta la fecha de pago del ciclo y
    30 días por cada cuota (tₖ = g + 30·k). Así, sin redondeos, la TCEA es igual a la TEA.
    Se resuelve por bisección, que siempre converge porque el valor presente baja cuando la
    tasa sube.
    """
    V0 = D(valor_recibido)
    if V0 <= 0 or not flujos:
        raise ErrorFinanciero("La TCEA necesita un valor recibido positivo y al menos un pago.")
    if any(dias <= 0 for dias, _ in flujos):
        raise ErrorFinanciero("Cada pago debe ocurrir al menos un día después de la compra.")
    plazos = [(D(dias) / D(DIAS_ANIO), D(monto)) for dias, monto in flujos]

    def exceso(r):  # valor presente de los pagos menos lo recibido
        return sum(monto / (UNO + r) ** t for t, monto in plazos) - V0

    bajo, alto = Decimal("-0.9999"), UNO
    while exceso(alto) > 0:
        alto *= 2
        if alto > Decimal("1E9"):
            raise ErrorFinanciero("La TCEA es demasiado alta para calcularse.")
    if exceso(bajo) < 0:
        raise ErrorFinanciero("Los pagos no alcanzan para devolver el valor recibido.")
    for _ in range(200):
        medio = (bajo + alto) / 2
        if exceso(medio) > 0:
            bajo = medio
        else:
            alto = medio
        if alto - bajo < Decimal("1E-30"):
            break
    return (bajo + alto) / 2


def flujos_de_cuotas(resultado):
    """Flujos (g + 30·k, cuota ₖ) de una compra en cuotas, para calcular su TCEA."""
    return [(resultado.dias_gracia + DIAS_MES * f.numero, f.cuota) for f in resultado.filas]


def flujos_de_mensual(resultado):
    """Flujo único (días, V) de una compra a fin de mes."""
    return [(resultado.dias, resultado.total)]


# ---------------------------------------------------------------------------
# Comparación de alternativas (ajuste A: "elegir la mejor alternativa")
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Alternativa:
    clave: str  # CONTADO, MENSUAL o CUOTAS_n
    nombre: str
    n_pagos: int
    cuota: Decimal | None
    total: Decimal
    costo_financiero: Decimal  # total − precio contado
    tcea: Decimal | None  # sobre el precio contado
    primer_pago: date | None


@_preciso
def comparar_alternativas(capital_lista, capital_contado, tasa, fecha_compra, ciclo, max_cuotas,
                          permite_mensual=True, permite_cuotas=True):
    """Compara pagar al contado, a fin de mes o en 1…n cuotas para la misma compra.

    La TCEA se calcula sobre el PRECIO CONTADO (lo que el cliente pagaría hoy), así que
    incluye el sobreprecio de lista además de los intereses.
    """
    contado = r2(capital_contado)
    lista = r2(capital_lista)
    salida = [Alternativa("CONTADO", "Contado (paga hoy)", 1, None, contado, r2(CERO), CERO, a_fecha_lima(fecha_compra))]
    if permite_mensual:
        m = compra_mensual(lista, tasa, fecha_compra, ciclo.fecha_pago)
        salida.append(Alternativa(
            "MENSUAL", f"Fin de mes ({ciclo.fecha_pago:%d/%m/%Y})", 1, None, m.total, m.total - contado,
            tcea(contado, flujos_de_mensual(m)), ciclo.fecha_pago,
        ))
    if permite_cuotas:
        for n in range(1, max_cuotas + 1):
            try:
                c = compra_en_cuotas(lista, tasa, fecha_compra, ciclo.fecha_pago, n)
            except ErrorFinanciero:
                continue  # monto muy pequeño para ese número de cuotas
            salida.append(Alternativa(
                f"CUOTAS_{n}", f"{n} cuota{'s' if n > 1 else ''}", n, c.cuota, c.total_pagado,
                c.total_pagado - contado, tcea(contado, flujos_de_cuotas(c)), c.filas[0].vencimiento,
            ))
    return salida
