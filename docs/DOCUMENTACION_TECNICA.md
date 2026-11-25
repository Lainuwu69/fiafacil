# Documentación técnica de FíaFácil — Punto 9 del informe (Sistema de información)

Este documento desarrolla el punto 9 (a–e) del enunciado: **cómo el diseño del Hito 1 se implementó como sistema funcional**. Cada sección se puede trasladar al informe, agregando las capturas de pantalla y de pgAdmin que se indican.

Todas las cifras se midieron sobre el sistema el 20/11/2026.

---

## 9a. Conectividad

### Arquitectura física (dónde está cada componente)

En la versión entregada, los tres componentes corren en **un mismo equipo**, que actúa como servidor local. Un navegador de otro equipo de la misma red también podría entrar si se configura `ALLOWED_HOSTS`.

```
┌─────────────────────────── Equipo servidor (Windows 11) ───────────────────────────┐
│                                                                                     │
│  ┌──────────────────────┐   HTTP 127.0.0.1:8000   ┌──────────────────────────────┐  │
│  │ Navegador            │ ──────────────────────▶ │ Servidor de aplicación       │  │
│  │ (Chrome / Edge,      │ ◀────────────────────── │ Django 5.2.19 (Python 3.13)  │  │
│  │  escritorio o        │   HTML + JSON + CSS/JS  │ manage.py runserver          │  │
│  │  celular)            │                         │ ~101 MB de RAM               │  │
│  └──────────────────────┘                         └──────────────┬───────────────┘  │
│                                                                  │ TCP 5432          │
│                                                                  │ psycopg 3 (SQL)   │
│                                                   ┌──────────────▼───────────────┐  │
│                                                   │ PostgreSQL 16.16             │  │
│                                                   │ servicio postgresql-x64-16   │  │
│                                                   │ base "fiafacil" (UTF8)       │  │
│                                                   │ ~118 MB de RAM               │  │
│                                                   └──────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

| Componente | Dónde está | Tecnología | Puerto |
|---|---|---|---|
| Aplicación (interfaz) | Navegador del usuario | HTML, CSS (Bootstrap 5.3.3 local), JavaScript sin framework | — |
| Servidor y API | Equipo servidor, carpeta del proyecto | Django 5.2.19 sobre Python 3.13.17 | 8000 (HTTP) |
| Base de datos | Equipo servidor, servicio de Windows | PostgreSQL 16.16 | 5432 (TCP, solo `localhost`) |
| Archivos subidos | Carpeta `media/` del servidor | Imágenes del catálogo (máximo 2 MB) | — |

**Despliegue opcional:** la misma arquitectura funciona en la nube, por ejemplo con Render o Railway y PostgreSQL administrado. Para eso se configura `DEBUG=False`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` y HTTPS en `.env`. `settings.py` ya activa las cookies seguras cuando `DEBUG=False`.

### Arquitectura lógica (capas)

```
Presentación   templates/*.html + static/js (compra.js, pago.js, condicion.js)
     │           Solo muestran datos; NO calculan nada financiero.
     ▼
Control        */views.py + core/portal.py      (rutas, permisos por rol, formularios)
     │         cuentas/middleware.py             (tienda activa de cada solicitud, RN01)
     │         cuentas/permisos.py               (negocio / cliente / plataforma)
     ▼
Negocio        creditos/servicios.py             (algoritmo del capítulo 4: transacciones,
     │                                            idempotencia, bloqueos, auditoría)
     ▼
Dominio        creditos/finanzas.py              (modelo matemático del capítulo 3; sin BD)
     ▼
Datos          */models.py → ORM de Django → PostgreSQL (15 tablas del capítulo 5)
```

### Cómo se comunican

| Origen → destino | Protocolo y formato | Ejemplos |
|---|---|---|
| Navegador → Django (pantallas) | HTTP GET/POST; formularios con token CSRF; respuesta HTML | `/ventas/nueva/`, `/clientes/<id>/pago/` |
| Navegador → Django (cálculo en vivo) | HTTP POST con cuerpo JSON y cabecera `X-CSRFToken`; respuesta JSON | `POST /compras/simular/` → corte, vencimiento, días, tasa, interés o cronograma, disponible, TCEA y alternativas |
| | | `POST /clientes/<id>/pago/calcular/` → mora, interés, capital y total de las obligaciones elegidas |
| | | `POST /clientes/api/tasa-equivalente/` → TEM y TEA de la tasa escrita |
| Django → PostgreSQL | TCP 5432 con psycopg 3; consultas SQL parametrizadas que genera el ORM, por lo que no hay inyección SQL | `SELECT … FOR UPDATE` al registrar ventas y pagos |

Los importes viajan en JSON como **texto** (`"604.37"`), no como número de punto flotante, para no perder decimales.

### Cómo se protege el acceso (login y contraseña)

| Medida | Implementación |
|---|---|
| Inicio de sesión obligatorio | Toda pantalla del negocio y del cliente exige sesión (`login_required` dentro de los decoradores por rol). Sin sesión, redirige a `/cuentas/login/`. |
| Contraseñas cifradas | Se guarda solo el hash PBKDF2 de Django, nunca la clave. Mínimo 8 caracteres y sin claves comunes ni solo números (validadores de Django). |
| Bloqueo por intentos fallidos | 5 intentos fallidos con el mismo correo en 15 minutos bloquean el acceso por 15 minutos (`cuentas/forms.py`). |
| Mensajes neutros | «Correo o contraseña incorrectos», sin revelar si el correo existe. |
| Sesión | Cookie `HttpOnly`, duración de 8 horas; en producción también `Secure`. El cierre de sesión solo se acepta por POST. |
| CSRF | Todo formulario y toda llamada JSON llevan token CSRF. |
| Clickjacking | `X_FRAME_OPTIONS = "DENY"`. |
| Roles en el servidor | `@negocio_requerido`, `@cliente_requerido` y `@plataforma_requerida`. Ocultar un botón no basta: el servidor responde 403 y lo audita. |
| Separación por tienda (RN01) | La tienda sale de la **membresía** del usuario (`TiendaActivaMiddleware`), no de la URL. Un registro de otra tienda responde 404 y queda auditado (`core/accesos.py`, `servicios.obtener_cuenta`). |
| Auditoría de accesos | Se registran inicio y cierre de sesión, intento fallido (con el correo, nunca la contraseña), acceso denegado, cambio de contraseña y la IP de origen. |
| Cambio de contraseña | Cada usuario cambia la suya (botón de la llave), confirmando la actual; la sesión sigue abierta y el cambio se audita. Si la olvida, el administrador de la plataforma la restablece en `/admin/`. |
| Secretos fuera del código | `SECRET_KEY` y la contraseña de la base viven en `.env`, que está excluido de git. |

### Políticas de red y administración

- PostgreSQL escucha en el puerto 5432 y solo debe aceptar conexiones de `localhost`, que es la configuración por defecto del instalador. No se abre ese puerto en el firewall.
- El servidor de desarrollo escucha en `127.0.0.1:8000`. Para atender a otros equipos de la red, se agrega su IP o nombre a `ALLOWED_HOSTS` y se abre solo el puerto 8000 en el firewall de Windows.
- En producción: HTTPS obligatorio (`SECURE_PROXY_SSL_HEADER` ya configurado), `DEBUG=False`, `CSRF_TRUSTED_ORIGINS` con el dominio y un usuario de base de datos propio con permisos solo sobre `fiafacil`, en lugar de `postgres`.
- Respaldos: ver 9b.

### Requisitos de hardware y software (para la presentación)

| Recurso | Medición en el equipo de desarrollo | Recomendado |
|---|---|---|
| RAM usada por el sistema | 101 MB (Django) + 118 MB (PostgreSQL) | 4 GB en el equipo servidor |
| Disco | Proyecto 1.6 MB, entorno virtual 67 MB, PostgreSQL 1,048 MB | 2 GB libres |
| Procesador | Intel Core i7-9750H | 64 bits, 2 núcleos o más |
| Sistema operativo | Windows 11 | Windows 10/11, macOS o Linux |
| Cliente | Navegador actual | Chrome, Edge o Firefox; celular desde 360 px de ancho |

**Captura sugerida para el informe:** el diagrama de arquitectura y la pantalla de login con un intento fallido.

---

## 9b. Base de datos

**Motor:** PostgreSQL 16.16, con la base `fiafacil` en codificación UTF8. Las tablas se crean a partir del modelo entidad-relación del capítulo 5 mediante las migraciones de Django (`python manage.py migrate`).

### Tablas implementadas (15 entidades del capítulo 5 + Anulación)

| Tabla | Entidad | Columnas | Función | Restricciones principales |
|---|---|---|---|---|
| `usuario` | Usuario | 10 | Acceso al sistema; id UUID; login por correo | Correo único sin distinguir mayúsculas |
| `membresia` | Membresía | 6 | Permiso de un usuario en una tienda con un rol | `UNIQUE(usuario, tienda, rol)`; rol NEGOCIO o CLIENTE |
| `tienda` | Tienda | 11 | Establecimiento de la plataforma | Código único (T001…); estado PENDIENTE, ACTIVA o INACTIVA; RUC nulo o de 11 dígitos |
| `articulo` | Artículo | 13 | Producto o servicio del catálogo | Precios > 0; imagen obligatoria; al menos una modalidad |
| `cuenta_cliente` | CuentaCliente | 13 | Cuenta corriente de un cliente en una tienda y moneda | `UNIQUE(tienda, documento, moneda)`; `UNIQUE(tienda, codigo)`; moneda PEN o USD |
| `condicion_credito` | CondiciónCrédito | 19 | Tasas, límite, plazo, corte y pago, versionados | `UNIQUE(cuenta, version)`; **una sola versión vigente**; corte 1–27; pago 2–28 y posterior al corte; plazo 1–60; capitalización solo en tasas nominales |
| `compra` | Compra | 24 | Venta al crédito con la versión de condiciones aplicada; marca `anulada` | `UNIQUE(tienda, numero)`; `UNIQUE(tienda, clave_idempotencia)`; corte posterior a la compra; modalidad coherente con las cuotas |
| `detalle_compra` | DetalleCompra | 10 | Líneas de la compra, con precios copiados | Cantidad, precio e importe > 0 |
| `obligacion` | Obligación | 15 | Pago mensual o cuota que vence en una fecha; estado PENDIENTE, PAGADA o ANULADA | `total = capital + interes`; pagada ⇔ tiene fecha de pago |
| `estado_cuenta` | EstadoCuenta | 10 | Listado de pago al corte, congelado | `UNIQUE(cuenta, corte)`; `total = capital + interes` |
| `estado_detalle` | EstadoDetalle | 10 | Líneas congeladas del estado | `UNIQUE(estado, obligacion)` |
| `pago` | Pago | 14 | Comprobante de un pago íntegro; marca `anulado` | `UNIQUE(tienda, clave_idempotencia)`; `total = mora + interes + capital` |
| `pago_aplicacion` | PagoAplicación | 9 | Cuánto del pago fue a mora, interés y capital | **Una sola aplicación vigente por obligación** (`UNIQUE(obligacion) WHERE anulada = false`): no se cobra dos veces |
| `anulacion` | Anulación (nueva) | 8 | Corrección trazable de un error de registro (sección 5.3): qué se anuló, motivo, quién y cuándo | Anula exactamente una venta o un pago; cada uno solo una vez |
| `auditoria` | Auditoría | 10 | Bitácora de todo lo que ocurre | Inmutable (no se edita ni se borra desde la aplicación) |
| `tope_tasa` | TopeTasa | 8 | Topes del BCRP con su fuente oficial | TEA > 0; vigencia coherente |

**Totales en PostgreSQL:** 16 tablas con sus claves primarias, 32 claves foráneas, 19 reglas de unicidad (14 `UNIQUE` y 5 índices únicos parciales o por expresión: correo sin distinguir mayúsculas, una sola condición vigente por cuenta, una aplicación vigente por obligación y una anulación por venta y por pago) y 64 restricciones `CHECK`.

**Corrección de errores (sección 5.3 del informe):** nada se borra. Una venta registrada por error se **anula** (solo si ninguna de sus obligaciones fue pagada): sus obligaciones pasan a ANULADA, dejan de cobrarse y liberan el crédito. Un pago se anula solo si es el **último** de la cuenta (orden inverso): sus obligaciones vuelven a PENDIENTE y pueden cobrarse otra vez. Cada anulación exige un motivo, queda en la tabla `anulacion` y en la auditoría. Un estado de cuenta ya generado no se altera: la línea aparece marcada como anulada y se muestra cuánto queda por cobrar.

**Tipos de datos (sección 2.5 del informe):** importes `NUMERIC(18,2)`, tasas `NUMERIC(20,15)` guardadas en decimal (24 % = 0.240000000000000), cantidades `NUMERIC(12,3)` y fechas y horas `TIMESTAMPTZ`. Nunca se usa punto flotante.

**Integridad (sección 5.3 del informe):**
- Claves foráneas con `PROTECT`: no se puede borrar un registro que tenga historial.
- Registros financieros **inmutables** (`core/modelos_base.py`). Compras, obligaciones, estados y pagos no se modifican ni se borran; solo cambian el estado de una obligación al pagarse y la fecha de fin de una versión de condiciones.
- Bajas **lógicas** (RN09) en tiendas, artículos, clientes y membresías.
- Las reglas que involucran varias filas se validan en el servidor, dentro de una transacción con bloqueo: límite de crédito, misma tienda y orden de las cuotas.

### Evidencia de que todo el proceso financiero queda registrado

Después de `python manage.py cargar_demo --con-operaciones`, ejecutar en pgAdmin (Query Tool sobre la base `fiafacil`) y capturar los resultados:

```sql
-- 1. Compras del juego A y B con su modalidad, capital, interés, total y TCEA
SELECT c.numero, cc.codigo, c.fecha_compra AT TIME ZONE 'America/Lima' AS fecha_lima, c.modalidad, c.n_cuotas,
       c.capital, c.interes, c.total, c.capital_con_gracia, c.cuota, round(c.tcea * 100, 7) AS tcea_pct
FROM compra c JOIN cuenta_cliente cc ON cc.id = c.cuenta_id ORDER BY c.numero;

-- 2. Obligaciones generadas (pago mensual o cuotas) y su estado
SELECT cc.codigo, c.numero AS compra, o.numero, o.tipo, o.vencimiento, o.capital, o.interes, o.total, o.saldo_final, o.estado
FROM obligacion o JOIN compra c ON c.id = o.compra_id JOIN cuenta_cliente cc ON cc.id = o.cuenta_id
ORDER BY cc.codigo, o.vencimiento, o.numero;

-- 3. Estado de cuenta de septiembre de C001: 200.00 + 1.90 = 201.90
SELECT cc.codigo, e.corte AT TIME ZONE 'America/Lima' AS corte, e.fecha_pago, e.capital, e.interes, e.total
FROM estado_cuenta e JOIN cuenta_cliente cc ON cc.id = e.cuenta_id ORDER BY e.corte, cc.codigo;

-- 4. Pagos y su aplicación en orden mora → interés → capital (C001: 0.08 + 1.90 + 200.00 = 201.98)
SELECT p.numero, cc.codigo, p.fecha_efectiva, a.dias_mora, a.mora, a.interes, a.capital, a.total
FROM pago p JOIN pago_aplicacion a ON a.pago_id = p.id JOIN cuenta_cliente cc ON cc.id = p.cuenta_id
ORDER BY p.numero;

-- 5. Auditoría del proceso
SELECT instante AT TIME ZONE 'America/Lima' AS instante, evento, descripcion FROM auditoria ORDER BY instante;
```

Las mismas tablas se pueden consultar, en modo de solo lectura, desde el **registro central** (`/admin/`, usuario `admin@fiafacil.pe`).

**Topes del BCRP (tabla `tope_tasa`):** cargados con `python manage.py cargar_topes_bcrp` desde las notas informativas oficiales del BCRP (Circular N.º 0008-2021-BCRP), tasa máxima de interés convencional compensatorio:

| Periodo | Moneda nacional | Moneda extranjera | Fuente |
|---|---|---|---|
| 01/05/2026 – 31/10/2026 | 114.13 % anual | 99.84 % anual | Nota del 01/04/2026 (copia en `docs/fuentes/`) |
| 01/11/2026 – 30/04/2027 | **114.68 % anual** | **103.14 % anual** | Nota del 01/10/2026 |

Se cargan los dos periodos porque las compras de los juegos A y B son de septiembre de 2026. Al guardar las condiciones de un cliente, el sistema compara la TEA equivalente de la tasa pactada con el tope de su moneda y la rechaza si lo supera. La nota no fija la tasa moratoria, por eso no se cargó un tope moratorio. Próxima actualización del BCRP: 1 de mayo de 2027.

### Plan de administración de la base

| Tarea | Cómo | Frecuencia |
|---|---|---|
| Respaldo | `.\scripts\respaldo.ps1` (`pg_dump` en formato comprimido; conserva los 7 últimos en `respaldos/`) | Antes de cada demo; a diario en uso real (Programador de tareas) |
| Restauración | `pg_restore -h localhost -U postgres -d fiafacil --clean --if-exists respaldos\ARCHIVO.dump` | Ante pérdida o daño |
| Cambios de estructura | Solo con migraciones de Django (`makemigrations` / `migrate`), versionadas en el código | En cada cambio del modelo |
| Estados de cuenta | Tarea programada de Windows «FiaFacil - generar estados» (`scripts\programar_tarea.ps1`), que ejecuta `manage.py generar_estados` (idempotente) y deja el resultado en `logs\generar_estados.log` | A diario a las 21:00 (después de la hora de corte); si el equipo estaba apagado, al encenderlo |
| Acceso | Usuario de base propio con permisos solo sobre `fiafacil` en producción; contraseña solo en `.env` | Al desplegar |

Un respaldo de prueba del 20/11/2026 pesó 86.7 KB.

---

## 9c. Código fuente

### Lenguajes y frameworks

Medido con `python scripts/medir_codigo.py`: líneas sin blancos ni comentarios, sin librerías de terceros.

| Lenguaje | Líneas | Archivos | Uso |
|---|---|---|---|
| Python | 5,150 | 76 | Modelo matemático, servicios, modelos, vistas, pruebas y comandos |
| HTML (plantillas Django) | 1,427 | 42 | Pantallas |
| JavaScript | 207 | 4 | Simulación en vivo, liquidación del pago, tasa equivalente y utilidades |
| PowerShell | 51 | 3 | Respaldo de la base y tarea programada |
| CSS | 46 | 1 | Estilos propios sobre Bootstrap |
| **Total** | **6,881** | | Además, 737 líneas de migraciones generadas por Django y el SQL que genera el ORM |

Frameworks y librerías: Django 5.2.19, psycopg 3.3.9, Pillow 13.0.0, python-dotenv 1.2.4, Bootstrap 5.3.3 y Bootstrap Icons 1.11.3.

### Estructura y componentes principales

| Componente | Archivo | Responsabilidad | Capítulo del informe |
|---|---|---|---|
| Modelo matemático | `creditos/finanzas.py` | Conversión de tasas, días exactos, ciclo de corte, compra mensual, gracia, cuota y cronograma franceses, mora, disponible, TCEA y alternativas. Sin base de datos y con `Decimal` de 40 dígitos. | 3 |
| Algoritmo transaccional | `creditos/servicios.py` | `calcular_compra`, `registrar_compra`, `generar_estado`, `calcular_pago`, `registrar_pago`, `anular_compra`, `anular_pago`, `guardar_condicion`, `exposicion`, `disponible`, `flujo_cobranzas`, `indicadores_cartera` | 4 |
| Modelos de datos | `*/models.py` | Las 15 entidades con sus restricciones | 5 |
| Seguridad | `cuentas/middleware.py`, `cuentas/permisos.py`, `core/accesos.py` | Tienda activa, roles y acceso ajeno = 404 auditado | 5.3 |
| Pantallas y API | `*/views.py`, `core/portal.py`, `templates/`, `static/js/` | Interfaz del negocio, de la plataforma y del cliente | 3.2 |
| Comandos | `cargar_demo`, `generar_estados` | Datos de los juegos A y B; generación diaria de estados | 3.4 |

**Cómo se registra una venta** (sigue el pseudocódigo 4.1):
1. El navegador envía las líneas a `/compras/simular/` y muestra la respuesta (no calcula nada).
2. Al confirmar, `registrar_compra` verifica que la cuenta sea de la tienda y revisa la clave de idempotencia.
3. Abre una transacción, bloquea la tienda y la cuenta (`select_for_update`), toma la versión de condiciones vigente en la fecha de la compra y recalcula todo con `finanzas.py`.
4. Verifica `E + nuevo capital ≤ límite`, graba la compra, sus líneas y sus obligaciones, y deja el evento en la auditoría.

### Esfuerzo, costo y tiempo (rúbricas ICACIT A a.c1 y ABET 1.c3)

**Estimación con COCOMO II** (modelo Post-Architecture, factores nominales; Boehm et al., 2000), con el tamaño medido de 6.881 KSLOC (25/11/2026):

| Variable | Fórmula | Resultado |
|---|---|---|
| Exponente | E = 0.91 + 0.01 × 18.97 | 1.0997 |
| Esfuerzo | PM = 2.94 × 6.881^1.0997 | **24.52 personas-mes** |
| Tiempo | TDEV = 3.67 × 24.52^0.3179 | **10.15 meses** |
| Personal promedio | PM / TDEV | 2.42 personas |

**Costo:** costo estimado = PM × costo mensual por persona. El grupo debe sustentar la tarifa mensual con una fuente. Este documento no fija un valor.

**Planificado frente a ejecutado:** el plan tenía 10 fases (CLAUDE.md, sección 6). Las fases 1 a 9 se ejecutaron el 19 y 20/11/2026 con asistencia de IA (Claude Code), como se detalla fase por fase en `docs/REGISTRO_IA.md`. El 25/11/2026 se completaron la anulación trazable, el cambio de contraseña y la tarea programada diaria. La diferencia frente a los 10.2 meses de COCOMO II se explica por esa asistencia y porque el diseño ya estaba completo en el Hito 1, y se debe declarar en la sección de uso de IA del informe. Los riesgos que ocurrieron y su contingencia están en `docs/RIESGOS.md`.

> Referencia: Boehm, B. W., Abts, C., Brown, A. W., Chulani, S., Clark, B. K., Horowitz, E., Madachy, R., Reifer, D. J., & Steece, B. (2000). *Software cost estimation with COCOMO II*. Prentice Hall.

---

## 9d. Ayuda y asistencia técnica

| Medio | Implementación | Dónde verlo |
|---|---|---|
| Ayuda en **cada campo** | `help_text` con ejemplo de formato en todos los campos, mostrado con un ícono ⓘ (tooltip) y como texto bajo el campo (`{% campo %}`, `parciales/campo.html`). Una prueba automática falla si un campo no tiene ayuda. | Cualquier formulario: registro, artículo, cliente, condiciones, venta, pago |
| Cálculo explicado en vivo | La venta muestra corte, vencimiento, días, tasa del periodo, cronograma, TCEA y disponible. El cliente muestra TEM y TEA mientras se escribe la tasa. El pago muestra la mora y el orden de aplicación. | Nueva venta, Nuevo cliente, Registrar pago |
| Mensajes de error concretos | Indican la causa y el dato, por ejemplo: «La compra excede el límite de crédito. Disponible: S/ 100.00; se necesita: S/ 100.01». | Cualquier validación |
| Ayuda general | Centro de ayuda `/ayuda/`, público: primeros pasos, perfiles, 11 fórmulas con ejemplos de los juegos A y B, indicadores, 10 preguntas frecuentes y glosario | Menú «Centro de ayuda», botón **?** y enlace en el login |
| Asistencia técnica | Botón flotante de **WhatsApp** en todas las páginas y **correo** de soporte, configurables en `.env` (`SOPORTE_WHATSAPP`, `SOPORTE_CORREO`) | Todas las pantallas |

---

## 9e. Validación y pruebas

### Validaciones (cuatro capas)

| Capa | Qué valida | Ejemplos |
|---|---|---|
| Navegador | Tipos y rangos básicos, sin cálculos | `type="date"` con máximo hoy; cantidades > 0; doble envío bloqueado (`data-un-envio`) |
| Formularios (servidor) | Formato y coherencia de cada campo | DNI de 8 dígitos; RUC de 11; día de pago posterior al corte; capitalización que divide al periodo; imagen JPG, PNG o WEBP de hasta 2 MB; contraseña segura |
| Servicios (servidor, en transacción) | Reglas de negocio RN01–RN12 | Límite de crédito (con Pg en cuotas); plazo máximo; fecha no futura; modalidad permitida por el artículo; ciclo con estado ya generado; cuotas en orden; pago exacto sin parciales; tope del BCRP; idempotencia; anulación solo sin pagos (venta) o del último pago, con motivo |
| Base de datos | Última defensa ante cualquier error | 64 `CHECK`, 19 reglas de unicidad y 32 claves foráneas (ver 9b) |

### Pruebas automáticas

`python manage.py test` ejecuta **176 pruebas**, todas en verde. Las pruebas usan una base PostgreSQL temporal que se crea y se borra sola.

| Archivo | Pruebas | Qué cubre |
|---|---|---|
| `creditos/test_finanzas.py` | 33 | Modelo matemático: juegos A y B, frontera, redondeo HALF_UP, conversión de tasas, convenciones, TCEA y alternativas |
| `creditos/test_servicios.py` | 30 | Juegos A y B grabados en la base; límite exacto; plazo; fecha futura; cambio de tasa; tope del BCRP; idempotencia; tienda ajena (404); ciclo cerrado; orden de cuotas; flujo |
| `cuentas/tests.py` | 20 | Registro, login, bloqueo por intentos, logout, cambio de contraseña, roles, flujo de la demo (registro → login → activación → panel) |
| `creditos/test_anulacion.py` | 13 | Anulación de ventas y pagos: libera crédito, no borra, exige motivo, orden inverso, se puede volver a cobrar, estado congelado marcado, indicadores, tienda ajena y permisos |
| `creditos/tests.py` | 16 | Restricciones de la base en compras, obligaciones, pagos y estados; inmutabilidad; existencia de las 15 tablas y tipos NUMERIC |
| `creditos/test_vistas.py` | 16 | Pantallas por HTTP: catálogo con imagen, clientes, API de simulación y de pago, juego A completo, panel, auditoría, ayuda en todos los campos |
| `clientes/tests.py` | 13 | Cuentas, monedas y calendario RN04; versionado de condiciones |
| `core/tests.py` | 13 | Configuración (PostgreSQL, hora de Lima, formatos peruanos), login por correo y centro de ayuda |
| `tiendas/tests.py` | 11 | Tiendas, artículos y membresías |
| `core/test_portal.py` | 6 | El cliente solo ve lo suyo; no puede operar |
| `core/test_demo.py` | 5 | `cargar_demo` reproduce los juegos A y B, es idempotente y pide confirmación para borrar; `cargar_topes_bcrp` carga los topes oficiales y una TEA de 120 % se rechaza |

### Resultados frente a los juegos de prueba del informe (sección 3.4)

| Caso | Esperado (informe) | Obtenido (sistema) |
|---|---|---|
| A: interés de las compras del 05/09 y 18/09 | 1.52 y 0.38 | 1.52 y 0.38 |
| A: estado de septiembre | 201.90 | 201.90 |
| A: pago el 01/10 (5 días de atraso) | mora 0.08, total 201.98 | 0.08 (0.05 + 0.03), 201.98 |
| A: pago de 150.00 | Rechazado | Rechazado («No se aceptan pagos parciales») |
| A: disponible después del pago | 950.00 | 950.00 |
| B: TEM y TEA | 0.02 y 0.268241794562545 | 0.020000000000000 y 0.268241794562545 |
| B: gracia, Pg, cuota | 11 días, 604.37, 209.57 | 11, 604.37, 209.57 |
| B: cronograma | 12.09 / 8.14 / 4.11; saldo 406.89 / 205.46 / 0.00 | Idéntico |
| B: total pagado | 628.71 | 628.71 |
| B: disponible | 395.63 y luego 593.11 | 395.63 y 593.11 |
| Frontera: 19:59:59 / 20:00:00 / 20:00:01 | 26/09 / 26/10 / 26/10 | Idéntico |
| Frontera: límite 100 | Acepta 100.00, rechaza 100.01 | Idéntico |
| Frontera: tasa 0 | Cuotas de 200 | 200.00 × 3 |
| Frontera: Pg 100, TEM 2 %, 3 cuotas | 34.68, 34.68, 34.67 | Idéntico |
| Frontera: 6 días de mora | 0.10 | 0.10 |
| Adicional: TCEA del juego B | — | 26.8273729 % |

### Pruebas manuales en el navegador

Durante el desarrollo se verificaron en el navegador, en escritorio y en celular:
- registro → login → tienda pendiente → activación → panel;
- venta del juego B con simulación en vivo;
- pago con 5 días de mora (0.09 sobre 209.57) y comprobante;
- TEM y TEA en vivo;
- portal del cliente (debe 419.14, disponible 593.11).

La verificación final (fase 10) repite el flujo completo de la exposición.

**Capturas sugeridas para el informe:** la salida de `python manage.py test`, la simulación de la venta del juego B, el estado de cuenta con la mora como ítem separado y el comprobante.
