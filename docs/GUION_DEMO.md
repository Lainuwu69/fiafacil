# Guion de la exposición — FíaFácil (Grupo 6, jueves 13:15–13:45)

Duración: **20 minutos + 5 de preguntas**. La distribución es referencial, pero hay que cubrir todos los puntos de la guía de la semana 15.

| Bloque | Tiempo | Contenido | Fuente |
|---|---|---|---|
| 1. Resumen ejecutivo del Hito 1 | 4 min | Problemática (apartado 2.6); acciones por Student Outcome; datos de entrada, salida e intermedios; fórmulas; modelo entidad-relación; algoritmo | Informe del Hito 1 corregido |
| 2. Desarrollo del sistema | 4 min | 9a Conectividad, 9b Base de datos, 9c Código fuente, 9d Ayuda, 9e Validación y pruebas | `docs/DOCUMENTACION_TECNICA.md` |
| 3. Demo en vivo | 12 min | Registro de un usuario nuevo → inicio de sesión → proceso financiero completo | Este guion |

Sugerencia de reparto (completar con nombres): cada integrante presenta un bloque y responde preguntas de su parte. Todos deben poder explicar `finanzas.py`, `servicios.py` y el modelo de datos.

| Integrante | Parte |
|---|---|
| ________ | Bloque 1: problemática y Student Outcomes |
| ________ | Bloque 1: fórmulas, modelo E-R y algoritmo |
| ________ | Bloque 2: 9a a 9e |
| ________ | Demo: minutos 0 a 6 (registro hasta ventas) |
| ________ | Demo: minutos 6 a 12 (cuotas, estado, pago, panel y portal) |

---

## Preparación (el día anterior y 30 minutos antes)

1. **Base limpia con los usuarios de la demo** (borra todo lo demás):
   ```powershell
   .\.venv\Scripts\python.exe manage.py cargar_demo --reiniciar --si
   ```
   Así quedan `admin@fiafacil.pe`, `rosa@bodega.pe` (T001 «Bodega Doña Rosa») y `carmen@cliente.pe`, sin operaciones. La tienda nueva de la demo será la **T002**.
2. Respaldo previo: `.\scripts\respaldo.ps1`.
3. `python manage.py test`: las 175 pruebas en verde (sirve también como captura).
4. Iniciar el servidor: `python manage.py runserver`.
5. Abrir **dos ventanas**: una normal (negocio) y una de **incógnito** (administrador y, al final, cliente). Zoom del navegador al 125 % para el proyector.
6. Dejar en el escritorio una imagen (JPG o PNG de menos de 2 MB) para el artículo.
7. Tener a mano los datos de esta hoja.
8. Plan B: si algo falla, entrar con `rosa@bodega.pe` (clave `Fiafacil-2026`), que tiene los mismos clientes C001 y C002 ya creados. Si falla todo, pasar el **video**.

---

## Demo en vivo (12 minutos)

### 0:00–1:30 · Registro de un usuario nuevo (obligatorio)
- Ventana normal → «Registra tu negocio».
- Datos: nombres **Ana**, correo **ana@panaderia.pe**, una contraseña segura, negocio **Panadería San Juan**, giro **Panadería**, dirección cualquiera.
- Mostrar la ayuda: el ícono ⓘ y el ejemplo debajo de cada campo. Provocar un error: un RUC de 5 dígitos da «El RUC debe tener 11 dígitos».
- Crear la cuenta → mensaje «Creamos tu usuario … y la tienda T002».

### 1:30–2:15 · Inicio de sesión con ese usuario (obligatorio) y activación
- Iniciar sesión con **ana@panaderia.pe** → aviso «Tu tienda está pendiente de activación».
- Ventana de incógnito → `admin@fiafacil.pe` → **Tiendas** → T002 → **Activar**.
- Volver a la ventana normal → «Volver a revisar» → aparece el **panel**.
- Frase clave: «Así se cumple el requisito 1: el administrador del sistema da de alta la tienda».

### 2:15–3:00 · Catálogo
- Catálogo → Nuevo artículo: **Consumo general**, unidad **Unidad**, precio contado **1.00**, precio de lista **1.00**, marcar **fin de mes** y **cuotas**, subir la imagen.
- Frase clave: «Lo valemos a S/ 1.00 para reproducir los montos de los juegos de prueba del informe».

### 3:00–4:15 · Cliente 1 (juego A) con condiciones
- Clientes → Nuevo cliente: DNI **45678912**, **Carmen Quispe Rojas**, moneda **Soles**.
- Condiciones: tasa **EFECTIVA 24**, periodo **Anual**; mora **EFECTIVA 3**, anual; límite **1000**; máximo de cuotas **3**; corte día **20** a las **20:00:00**; pago día **26**; **vigente desde 01/09/2026 00:00**.
- Mostrar la equivalencia en vivo: **TEM 1.8087582 %**. Explicar por qué la TEA no se divide entre 12.

### 4:15–6:00 · Ventas a fin de mes (juego A) y límite
- Nueva venta → Carmen, **Consumo general × 120**, fecha **05/09/2026 10:00**, fin de mes → la simulación muestra **corte 20/09 20:00, vence 26/09, 21 días, interés 1.52** → Confirmar.
- **× 80** el **18/09/2026 10:00** → interés **0.38** → Confirmar.
- Frontera (sin confirmar): cambiar la fecha a **20/09/2026 19:59:59** (vence el 26/09) y luego a **20:00:00** (vence el **26/10**): «RN03, comparación estricta en hora de Lima».
- **× 50** el **21/09/2026 10:00** → vence el **26/10** (pasa a octubre) → Confirmar.
- Intentar **× 900** → «La compra excede el límite de crédito. Disponible: S/ 750.00; se necesita: S/ 900.00». El botón se desactiva.

### 6:00–7:30 · Cliente 2 y venta en cuotas (juego B)
- Nuevo cliente: DNI **87654321**, **Pedro Huamán Salas**; tasa **NOMINAL 24**, anual, capitalización **Mensual** (TEM 2.0000000 %, TEA 26.8241795 %); el resto igual que Carmen.
- Nueva venta → Pedro, **× 600**, **15/09/2026 10:00**, **en cuotas, 3** → **11 días de gracia, Pg 604.37, cuota 209.57**, cronograma 26/10, 26/11 y 26/12 con saldos 406.89, 205.46 y 0.00; **total 628.71**; TCEA **26.8273729 %**; disponible 1,000.00 → **395.63**.
- Abrir «Comparar alternativas» (contado, fin de mes, 1 a 3 cuotas) → Confirmar → detalle con el cronograma.

### 7:30–8:30 · Estado de cuenta (requisito 6)
- Clientes → Carmen → «Estados de cuenta por ciclo» → corte 20/09 → listado ordenado por fecha: **200.00 + 1.90 = 201.90**, a pagar el 26/09.
- Proyectar la mora al **01/10/2026** → ítem separado «Intereses por mora: **0.08**».
- **Generar estado** → queda congelado (`UNIQUE(cuenta, corte)`).

### 8:30–10:00 · Pago con mora y sin pagos parciales
- Registrar pago → marcar las 2 obligaciones del 26/09, fecha **01/10/2026** → liquidación: **mora 0.08 → interés 1.90 → capital 200.00 = 201.98**.
- Escribir **150.00** → rechazo: «No se aceptan pagos parciales…».
- «Usar el total» → **201.98** → comprobante N° 000001 → disponible de Carmen: **950.00**.
- (Opcional) Pedro: pagar la cuota 1 el 26/10 → 209.57 → disponible **593.11**.

### 10:00–11:00 · Panel, flujo de caja y auditoría
- Panel: capital por cobrar, vencido (la compra de 50 que vencía el 26/10), **índice de morosidad**, **periodo promedio de cobro** y **flujo de caja proyectado** por mes.
- Auditoría: registro, login, activación, compras, compra rechazada, pago rechazado y pago.

### 11:00–12:00 · Portal del cliente
- Carmen → «Acceso al portal» → correo **carmen.demo@cliente.pe** + contraseña inicial.
- Ventana de incógnito → iniciar sesión como Carmen → ve **solo su cuenta**: deuda, disponible, compras, estado y comprobante. No puede vender ni cobrar.
- Cierre: «Todo el proceso quedó registrado en PostgreSQL» y mostrar `/admin/` o pgAdmin si queda tiempo.

---

## Cuidados durante la demo

- **Orden:** registrar todas las compras de un ciclo **antes** de generar su estado de cuenta. Después el sistema rechaza compras en ese ciclo («ya fue generado»).
- **Fechas:** las ventas usan fechas pasadas. Funciona porque las condiciones rigen desde el 01/09/2026 («vigente desde»).
- **Doble clic:** no duplica nada (clave de idempotencia); si pasa, se puede mostrar como fortaleza.

## Preguntas probables (preparar la respuesta)

| Pregunta | Respuesta corta | Dónde está |
|---|---|---|
| ¿Por qué la TEA no se divide entre 12? | Porque las tasas efectivas se convierten por equivalencia de factores: TEM = (1 + TEA)^(30/360) − 1 | `finanzas.Tasa.efectiva` |
| ¿Qué pasa si se compra justo a la hora del corte? | Pasa al ciclo siguiente: la comparación es estricta (RN03) y en hora de Lima | `finanzas.ciclo_de_compra` |
| ¿Por qué se capitaliza la gracia? | Lo exige el enunciado: los intereses de la gracia se suman al capital antes de calcular la cuota | `finanzas.capital_con_gracia` |
| ¿Cómo se calcula la mora? | Sobre el total que debió pagarse, por los días de atraso, con la tasa moratoria; aparece como ítem aparte | `servicios._liquidar` |
| ¿Por qué el límite se compara con 604.37 y no con 600? | RN06: la exposición en cuotas incluye la gracia capitalizada | `servicios.calcular_compra` |
| ¿Cómo evitan que una tienda vea datos de otra? | La tienda sale de la membresía del usuario, no de la URL; lo ajeno da 404 y se audita | `cuentas/middleware.py`, `core/accesos.py` |
| ¿Qué pasa si dos personas venden al mismo tiempo? | La transacción bloquea la cuenta (`select_for_update`): la segunda espera y vuelve a verificar el límite | `servicios.registrar_compra` |
| ¿Por qué no usan float? | Porque no representa exactamente 0.10; se usa Decimal de 40 dígitos y redondeo HALF_UP | `finanzas.r2` |
| ¿Y si se equivocan al registrar una venta o un pago? | No se borra: se anula con motivo (RN09). La venta se anula si no tiene pagos; los pagos se anulan del último al primero; todo queda en la tabla `anulacion` y en la auditoría | `servicios.anular_compra`, `servicios.anular_pago` |
| ¿Quién genera los estados de cuenta en la fecha de corte? | Una tarea programada de Windows ejecuta `generar_estados` cada noche a las 21:00; también se pueden generar desde la pantalla | `scripts/programar_tarea.ps1` |
| ¿Qué es la TCEA y para qué sirve? | El costo efectivo anual: la TIR de los pagos; permite comparar alternativas (rúbrica del logro del curso) | `finanzas.tcea` |
| ¿Dónde usaron IA y en qué porcentaje? | Ver la sección de uso de IA del informe | `docs/REGISTRO_IA.md` |
