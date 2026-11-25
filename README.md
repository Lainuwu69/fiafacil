# FíaFácil

**Gestión de cuentas corrientes y créditos de pequeños comercios.** Reemplaza el cuaderno de fiados de bodegas, panaderías, pollerías, peluquerías, spa y otros negocios de barrio. Es una plataforma web **multitienda** que se ve desde el punto de vista del comercio que da el crédito.

Trabajo final del curso SI642 Finanzas e Ingeniería Económica (UPC, 2026-20), Grupo 6, sección 7696.

**Repositorio:** <https://github.com/Lainuwu69/fiafacil>

## Qué hace

- **Plataforma:** el administrador activa o da de baja las tiendas que se registran.
- **Negocio:** catálogo con imagen y precios contado/lista; clientes con tasa nominal o efectiva, moneda, límite, plazo, corte y pago; ventas a fin de mes o en cuotas (método francés vencido con gracia total) con simulación en vivo; estados de cuenta al corte (también automáticos cada noche); pagos íntegros con mora y comprobante; **anulación trazable** de ventas y pagos registrados por error; panel con indicadores y flujo de caja proyectado; auditoría.
- **Todos los usuarios:** cambio de su propia contraseña (botón de la llave).
- **Cliente:** portal de solo consulta con su deuda, crédito disponible, compras, estados y comprobantes.
- **Ayuda:** ícono ⓘ con ejemplo en cada campo, centro de ayuda en `/ayuda/` y soporte por WhatsApp y correo.

## Tecnologías

| Capa | Tecnología |
|---|---|
| Lenguajes | Python 3.13, JavaScript (sin framework), SQL (PostgreSQL), HTML y CSS |
| Framework web | Django 5.2.19 |
| Base de datos | PostgreSQL 16.16, conexión con psycopg 3.3.9 |
| Interfaz | Bootstrap 5.3.3 y Bootstrap Icons 1.11.3, guardados en `static/vendor` (funciona sin internet) |
| Imágenes | Pillow 13.0.0 |
| Configuración | python-dotenv 1.2.4 (archivo `.env`) |

## Requisitos

**Software:** Windows 10/11, macOS o Linux; Python 3.11 o superior (probado con 3.13.17); PostgreSQL 16 (probado con 16.16) o Docker; un navegador actual (Chrome, Edge o Firefox).

**Hardware (medido en el equipo de desarrollo):**

| Recurso | Medición | Recomendado |
|---|---|---|
| Memoria RAM en uso | 101 MB (Django) + 118 MB (PostgreSQL) ≈ 220 MB | 4 GB de RAM en el equipo |
| Disco | Proyecto 1.6 MB + entorno virtual 67 MB + PostgreSQL 1,048 MB | 2 GB libres |
| Procesador | Desarrollado en un Intel Core i7-9750H | Cualquier procesador de 64 bits de 2 núcleos |
| Clientes | Navegador de escritorio o celular | Pantalla desde 360 px de ancho |

## Compartir el proyecto con el grupo

**Quien lo comparte:** en la carpeta del proyecto ejecuta `.\scripts\empaquetar.ps1` y envía el archivo `entrega\FiaFacil_codigo_fuente.zip` (unos 650 KB) por Drive, WhatsApp o USB. El zip **no** incluye:
- `.env` (contraseñas): cada uno crea el suyo;
- `.venv`: se instala en cada computadora;
- los respaldos y las imágenes subidas: se regeneran.

**Con GitHub (más simple):** cada integrante descarga el proyecto desde <https://github.com/Lainuwu69/fiafacil>, con **Code → Download ZIP** o con:
```powershell
git clone https://github.com/Lainuwu69/fiafacil.git
```

**Quien lo recibe:** descomprime el zip (por ejemplo, en el Escritorio) y sigue la **instalación paso a paso** de abajo dentro de la carpeta `FiaFacil`. Usa **su propia contraseña de PostgreSQL** en su `.env`. Toma unos 20 minutos. Después puede practicar con [docs/TUTORIAL_JUEGOS_AB.md](docs/TUTORIAL_JUEGOS_AB.md).

Cada computadora tiene **su propia base de datos**: lo que uno registra no aparece en la de los demás.

## Instalación paso a paso (Windows, PowerShell)

1. **Instalar PostgreSQL 16** y anotar la contraseña del usuario `postgres`:
   ```powershell
   winget install -e --id PostgreSQL.PostgreSQL.16 --interactive
   ```
   Alternativa con Docker: `docker compose up -d` (usa `docker-compose.yml`).

2. **Crear el entorno virtual e instalar las dependencias** (en la carpeta del proyecto):
   ```powershell
   py -3.13 -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

3. **Configurar el archivo `.env`:**
   ```powershell
   Copy-Item .env.example .env
   ```
   Abre `.env` y completa `DB_PASSWORD` con la contraseña de `postgres` y `SECRET_KEY` con una clave aleatoria:
   ```powershell
   .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(50))"
   ```
   Cambia también `SOPORTE_WHATSAPP` y `SOPORTE_CORREO` por los canales reales de soporte.

4. **Crear la base de datos** `fiafacil`:
   ```powershell
   & "C:\Program Files\PostgreSQL\16\bin\createdb.exe" -h localhost -U postgres -E UTF8 fiafacil
   ```

5. **Crear las tablas y cargar los topes de tasa del BCRP:**
   ```powershell
   .\.venv\Scripts\python.exe manage.py migrate
   ```
   ```powershell
   .\.venv\Scripts\python.exe manage.py cargar_topes_bcrp
   ```

6. **(Opcional) Programar la generación diaria de estados de cuenta:**
   ```powershell
   .\scripts\programar_tarea.ps1
   ```

7. **Cargar los datos de demostración:**
   ```powershell
   .\.venv\Scripts\python.exe manage.py cargar_demo
   ```
   - Sin opciones: usuarios, tienda, catálogo y clientes C001 y C002, **sin operaciones** (para hacer la demo desde cero).
   - `--con-operaciones`: registra además las compras, estados y pagos de los juegos A y B.
   - `--reiniciar --si`: **borra todos los datos** y vuelve a cargar la demo.

8. **Iniciar el servidor** y abrir <http://127.0.0.1:8000>:
   ```powershell
   .\.venv\Scripts\python.exe manage.py runserver
   ```

## Usuarios de demostración

Clave para todos: `Fiafacil-2026`.

| Usuario | Perfil |
|---|---|
| `admin@fiafacil.pe` | Administrador de la plataforma (también entra a `/admin/`) |
| `rosa@bodega.pe` | Negocio: tienda T001 «Bodega Doña Rosa» |
| `carmen@cliente.pe` | Cliente: portal de la cuenta C001 |

C001 (Carmen) tiene las condiciones del **juego A** (TEA 24 %, fin de mes) y C002 (Pedro) las del **juego B** (TNA 24 % con capitalización mensual, cuotas). El artículo «Consumo general» vale S/ 1.00 por unidad, así que vender 120 unidades reproduce una compra de S/ 120.00.

## Comandos útiles

| Comando | Para qué sirve |
|---|---|
| `python manage.py test` | Ejecuta las 176 pruebas automáticas (deben pasar todas). |
| `python manage.py cargar_topes_bcrp` | Carga los topes de tasa compensatoria del BCRP (notas informativas oficiales): mayo–octubre 2026 (114.13 % / 99.84 %) y noviembre 2026 – abril 2027 (114.68 % / 103.14 %). Idempotente. |
| `.\scripts\empaquetar.ps1` | Genera `entrega\FiaFacil_codigo_fuente.zip` para compartir o entregar el código (sin `.env`, `.venv`, respaldos ni imágenes subidas). |
| `python manage.py generar_estados` | Genera los estados de cuenta de los cortes ya cumplidos (idempotente). |
| `.\scripts\programar_tarea.ps1` | Programa en Windows la tarea diaria «FiaFacil - generar estados» (21:00; si la laptop estaba apagada, se ejecuta al encenderla). Con `-Quitar` la elimina. El resultado queda en `logs/generar_estados.log`. |
| `python manage.py cargar_demo [--con-operaciones]` | Carga los datos de demostración. |
| `.\scripts\respaldo.ps1` | Respaldo de la base con `pg_dump` en `respaldos/` (conserva los 7 últimos). |
| `python scripts/medir_codigo.py` | Cuenta líneas de código y estima el esfuerzo con COCOMO II. |

## Estructura del proyecto

```
config/      configuración (lee .env), rutas y formatos peruanos (punto decimal, dd/mm/aaaa)
cuentas/     usuario (login por correo), membresías, registro, login, middleware y permisos por rol
tiendas/     tiendas (plataforma) y catálogo de artículos
clientes/    cuentas de clientes y condiciones de crédito versionadas; API de tasa equivalente
creditos/    finanzas.py (modelo matemático), servicios.py (algoritmo transaccional), compras,
             obligaciones, estados de cuenta, pagos, vistas y API de simulación
core/        auditoría, topes BCRP, panel, portal del cliente, ayuda, registro central (/admin/), cargar_demo
templates/   plantillas HTML;   static/   CSS, JavaScript y librerías locales
docs/        documentación técnica, guion de la demo, riesgos y registro del uso de IA
scripts/     respaldo de la base, generación diaria de estados (tarea programada) y medición del código
```

Más detalle en [docs/DOCUMENTACION_TECNICA.md](docs/DOCUMENTACION_TECNICA.md).

## Solución de problemas

| Síntoma | Causa probable y solución |
|---|---|
| `password authentication failed for user "postgres"` | La contraseña de `.env` (`DB_PASSWORD`) no coincide con la del instalador de PostgreSQL. |
| `database "fiafacil" does not exist` | Falta el paso 4 (crear la base). |
| `connection refused` en el puerto 5432 | El servicio de PostgreSQL está detenido: `Start-Service postgresql-x64-16`. |
| Las imágenes del catálogo no se ven | Con `DEBUG=False` Django no sirve `media/`; en desarrollo usa `DEBUG=True`. |
| «Demasiados intentos fallidos» al iniciar sesión | Bloqueo de seguridad de 15 minutos tras 5 intentos fallidos. |
