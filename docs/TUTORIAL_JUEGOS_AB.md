# Tutorial: entrar a FíaFácil y reproducir los juegos de prueba A y B

Este tutorial explica cómo encender el sistema, iniciar sesión y reproducir en pantalla los **juegos de prueba A y B** del informe (sección 3.4). Al final de cada paso se indica el **resultado que debe salir**, para comprobar que coincide con el informe.

Tiempo aproximado: 20 minutos la primera vez y 10 minutos cuando ya se conoce el recorrido.

---

## Parte 1. Encender el sistema

PostgreSQL arranca solo con Windows. Solo hay que iniciar el servidor de FíaFácil.

1. Abre **PowerShell** (tecla Windows → escribe *PowerShell* → Enter).
2. Entra a la carpeta del proyecto:
   ```powershell
   cd "C:\Users\user\OneDrive\Desktop\Finanzas"
   ```
3. Deja la base de datos lista para practicar (borra lo que haya y carga los usuarios, la tienda y los clientes de la demo):
   ```powershell
   .\.venv\Scripts\python.exe manage.py cargar_demo --reiniciar --si
   ```
   Debe decir: `Demo lista: T001 «Bodega Doña Rosa», clientes C001 y C002.`
4. Inicia el servidor:
   ```powershell
   .\.venv\Scripts\python.exe manage.py runserver
   ```
   Debe terminar con: `Starting development server at http://127.0.0.1:8000/`. **No cierres esta ventana** mientras uses el sistema; para apagarlo, presiona `Ctrl + C`.
5. Abre el navegador (Chrome o Edge) en **http://127.0.0.1:8000**. Aparece la pantalla **Iniciar sesión**.

## Parte 2. Usuarios para entrar

Clave para todos: **`Fiafacil-2026`**.

| Correo | Qué es | Qué puede hacer |
|---|---|---|
| `rosa@bodega.pe` | Dueña de la tienda T001 «Bodega Doña Rosa» | Vender, cobrar, ver estados, panel y auditoría. **Con este usuario se hacen los juegos A y B.** |
| `carmen@cliente.pe` | Clienta (cuenta C001) | Solo consultar su deuda, sus compras, sus estados y sus comprobantes |
| `admin@fiafacil.pe` | Administrador de la plataforma | Activar o dar de baja tiendas; ver el registro central en `/admin/` |

La tienda ya tiene todo preparado:

| Dato | Valor |
|---|---|
| Artículo | **Consumo general**, a **S/ 1.00** por unidad. Vender 120 unidades equivale a una compra de S/ 120.00 |
| Cliente **C001 · Carmen Quispe Rojas** | Condiciones del **juego A**: TEA 24 %, mora TEA 3 %, límite S/ 1,000, hasta 3 cuotas, corte el día 20 a las 20:00, pago el día 26 |
| Cliente **C002 · Pedro Huamán Salas** | Condiciones del **juego B**: TNA 24 % con capitalización mensual; el resto, igual que C001 |
| Vigencia de las condiciones | Desde el 01/09/2026, por eso se pueden registrar compras con fechas de septiembre |

**Inicia sesión** con `rosa@bodega.pe` y `Fiafacil-2026`. Entrarás al **Panel** de Bodega Doña Rosa.

> En cada campo hay un ícono **ⓘ**: si pasas el mouse encima, explica qué escribir y da un ejemplo.

---

## Parte 3. Juego A — TEA 24 %, pago a fin de mes

### Paso A1. Primera compra: 120 el 05/09/2026

1. Menú izquierdo → **Nueva venta**.
2. **Cliente:** `C001 · Carmen Quispe Rojas (PEN)`.
3. **Fecha y hora de la compra:** `05/09/2026 10:00`.
4. **Modalidad:** *Pago a fin de mes (fecha de pago)*.
5. **Artículo:** *Consumo general* · **Cantidad:** `120`.
6. Mira el cuadro **Resultado del cálculo** de la derecha (lo calcula el servidor mientras escribes):

   | Dato | Debe salir |
   |---|---|
   | Corte del ciclo | 20/09/2026 20:00 |
   | Vence (fecha de pago) | 26/09/2026 |
   | Días financiados | **21** |
   | Tasa del periodo i(21) | 1.2627222 % |
   | Interés | **S/ 1.52** |
   | Total a pagar | S/ 121.52 |
   | Disponible antes → después | S/ 1,000.00 → S/ 880.00 |

7. Presiona **Confirmar venta**. Se abre el detalle de la **Compra N° 1**.

### Paso A2. Segunda compra: 80 el 18/09/2026

Repite el paso A1 con fecha `18/09/2026 10:00` y cantidad `80`.

| Dato | Debe salir |
|---|---|
| Vence | 26/09/2026 |
| Días financiados | **8** |
| Interés | **S/ 0.38** |

Confirma la venta.

### Paso A3 (opcional). Prueba de frontera de la hora de corte

Antes de registrar la tercera compra, en **Nueva venta** con C001 y cantidad `10`, cambia solo la fecha y mira el vencimiento **sin confirmar**:

| Fecha y hora | Vence | Por qué |
|---|---|---|
| `20/09/2026 19:59:59` | **26/09/2026** | Antes del corte → ciclo de septiembre |
| `20/09/2026 20:00:00` | **26/10/2026** | A la hora exacta del corte → ciclo siguiente (RN03) |

Sal sin confirmar (por ejemplo, haz clic en **Panel**).

### Paso A4. Tercera compra: 50 el 21/09/2026 (pasa a octubre)

Nueva venta → C001, fecha `21/09/2026 10:00`, cantidad `50`, fin de mes.

| Dato | Debe salir |
|---|---|
| Corte del ciclo | **20/10/2026 20:00** |
| Vence | **26/10/2026**: la compra pasa al ciclo de octubre |
| Días financiados | 35 |

Confirma la venta.

### Paso A5 (opcional). Intentar superar el límite

Nueva venta → C001, fecha `22/09/2026 10:00`, cantidad `900`. Debe salir en rojo:

> La compra excede el límite de crédito. Disponible: S/ 750.00; se necesita: S/ 900.00.

El botón **Confirmar venta** queda desactivado. Sal sin confirmar.

### Paso A6. Estado de cuenta de septiembre

1. Menú → **Clientes** → en C001, botón **Ver**.
2. En **Estados de cuenta por ciclo**, junto a *Corte 20/09/2026 20:00*, presiona **Ver**.
3. Debe salir el listado de pago ordenado por fecha:

   | # | Compra | Días | Capital | Interés | Total |
   |---|---|---|---|---|---|
   | 1 | 05/09/2026 10:00 | 21 | 120.00 | 1.52 | 121.52 |
   | 2 | 18/09/2026 10:00 | 8 | 80.00 | 0.38 | 80.38 |
   | | **Total a pagar el 26/09/2026** | | **200.00** | **1.90** | **201.90** |

4. Debajo, en **Proyectar la mora al día**, elige `01/10/2026` → **Calcular**. Aparece un ítem separado: **Intereses por mora … 5 días de atraso: S/ 0.08**.
5. Presiona **Generar estado**. Queda «Generado · importes congelados».

> **Importante:** registra todas las compras de un ciclo **antes** de generar su estado. Después, el sistema rechaza compras en ese ciclo.

### Paso A7. Pago con 5 días de atraso

1. En la ficha de C001 → **Registrar pago**.
2. Marca las **dos** obligaciones que vencen el **26/09/2026** (compras N° 1 y N° 2).
3. **Fecha efectiva del pago:** `01/10/2026`.
4. La liquidación debe mostrar:

   | Concepto | Importe |
   |---|---|
   | 1. Intereses por mora | **S/ 0.08** (0.05 + 0.03) |
   | 2. Interés compensatorio | S/ 1.90 |
   | 3. Capital | S/ 200.00 |
   | **Total a pagar** | **S/ 201.98** |

5. **Prueba del pago parcial:** escribe `150.00` en *Importe recibido* → **Registrar pago**. Debe rechazarse con el mensaje «Pago rechazado: el total a pagar es S/ 201.98 y se recibió S/ 150.00. No se aceptan pagos parciales…».
6. Presiona **Usar el total** (pone `201.98`) → **Registrar pago**. Se abre el **Comprobante N° 000001**.

### Paso A8. Disponible después del pago

Menú → **Clientes**. En C001 debe salir **Disponible: S/ 950.00**. Solo queda pendiente la compra de 50 de octubre.

✅ **Juego A completo:** 1.52 · 0.38 · 201.90 · 0.08 · 201.98 · 150.00 rechazado · 950.00.

---

## Parte 4. Juego B — TNA 24 % con capitalización mensual, 3 cuotas

### Paso B1. Compra de 600 en 3 cuotas el 15/09/2026

1. **Nueva venta** → Cliente `C002 · Pedro Huamán Salas (PEN)`.
2. Fecha `15/09/2026 10:00`.
3. Modalidad: **En cuotas mensuales (método francés)** → **Número de cuotas:** `3`.
4. Artículo *Consumo general*, cantidad `600`.
5. El resultado debe mostrar:

   | Dato | Debe salir |
   |---|---|
   | Fin de la gracia (G) | 26/09/2026 |
   | Días de gracia total | **11** |
   | TEM | **2.0000000 %** |
   | Capital tras la gracia (Pg) | **S/ 604.37** |
   | Cuota | **S/ 209.57** |
   | TCEA | 26.8273729 % |
   | Disponible antes → después | S/ 1,000.00 → **S/ 395.63** |

   Y el cronograma:

   | N° | Vence | Saldo | Interés | Amortización | Cuota | Saldo final |
   |---|---|---|---|---|---|---|
   | 1 | 26/10/2026 | 604.37 | **12.09** | 197.48 | 209.57 | **406.89** |
   | 2 | 26/11/2026 | 406.89 | **8.14** | 201.43 | 209.57 | **205.46** |
   | 3 | 26/12/2026 | 205.46 | **4.11** | 205.46 | 209.57 | **0.00** |
   | | | | **24.34** | | **628.71** | |

6. (Opcional) Abre **Comparar alternativas de pago** para ver contado, fin de mes y 1 a 3 cuotas con su TCEA.
7. **Confirmar venta**.

### Paso B2. Pagar la primera cuota a tiempo

1. Clientes → C002 → **Registrar pago**.
2. Marca **Cuota 1** (vence el 26/10/2026) → fecha efectiva `26/10/2026`.
3. Debe salir **mora 0.00**, interés 12.09, capital 197.48, total **209.57**.
4. **Usar el total** → **Registrar pago**.

### Paso B3. Disponible después de la primera cuota

Menú → **Clientes**. En C002 debe salir **Disponible: S/ 593.11**.

✅ **Juego B completo:** 11 días · 604.37 · 209.57 · 12.09 / 8.14 / 4.11 · 628.71 · 395.63 · 593.11.

---

## Parte 5. Ver lo mismo como clienta (portal)

1. Arriba a la derecha → **Salir**.
2. Inicia sesión con `carmen@cliente.pe` y `Fiafacil-2026`.
3. Verás **solo su cuenta**: lo que debe, su crédito disponible (S/ 950.00), sus compras, su estado de septiembre (con la mora de 0.08 como ítem aparte) y su comprobante. No puede vender ni cobrar.

## Parte 6. Pruebas de frontera que no hace falta hacer a mano

Las pruebas automáticas ya comprueban todos los casos de frontera del informe (límite exacto de 100.00 y 100.01, tasa 0, cuotas de 34.68 / 34.68 / 34.67, mora de 0.10 por 6 días). Para verlas pasar, en otra ventana de PowerShell dentro de la carpeta:

```powershell
.\.venv\Scripts\python.exe manage.py test creditos.test_finanzas -v 2
```

Debe terminar en **OK**. Cada línea dice qué caso se probó.

## Parte 7. Atajos

| Quiero… | Comando (en la carpeta del proyecto, con el servidor apagado o en otra ventana) |
|---|---|
| Ver los juegos A y B ya registrados, sin hacerlos a mano | `.\.venv\Scripts\python.exe manage.py cargar_demo --reiniciar --si --con-operaciones` |
| Volver a empezar desde cero | `.\.venv\Scripts\python.exe manage.py cargar_demo --reiniciar --si` |
| Respaldar la base antes de practicar | `.\scripts\respaldo.ps1` |

## Si algo sale mal

| Problema | Solución |
|---|---|
| El navegador dice «No se puede acceder a este sitio» | El servidor no está encendido: repite el paso 4 de la parte 1 y no cierres esa ventana. |
| «Correo o contraseña incorrectos» | Revisa que la clave sea `Fiafacil-2026`, con F mayúscula. Después de 5 intentos fallidos se bloquea 15 minutos. |
| Al vender sale «El estado de cuenta del corte … ya fue generado» | Generaste el estado antes de registrar todas las compras de ese ciclo. Vuelve a empezar con `cargar_demo --reiniciar --si`. |
| Al vender sale «La cuenta no tenía condiciones de crédito vigentes en la fecha de la compra» | La fecha es anterior al 01/09/2026. Usa las fechas del tutorial. |
| Los importes no coinciden | Revisa la **hora** (10:00), la **modalidad** y que el cliente sea el correcto (C001 para A, C002 para B). |
| Error de conexión con la base de datos | El servicio de PostgreSQL está detenido: tecla Windows → *Servicios* → `postgresql-x64-16` → Iniciar. |
