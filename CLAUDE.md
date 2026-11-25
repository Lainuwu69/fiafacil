# CLAUDE.md — FíaFácil (Trabajo Final SI642, Grupo 6, sección 7696, 2026-20)

Este archivo da contexto a Claude Code para **construir desde cero** el sistema del Hito 2: qué pide el curso, qué se diseñó en el Hito 1 (que el código debe respetar), cómo se corrigió el informe y qué arquitectura construir. **La carpeta está vacía al empezar: no existe código previo.** Léelo completo y sigue el plan de la sección 6.

---

## 1. Contexto del curso

- **Curso:** SI642 Finanzas e Ingeniería Económica, UPC, Ingeniería de Sistemas de Información.
- **Logro:** identificar, formular y resolver problemas de gerencia financiera aplicando ciencia y matemática para desarrollar programas de cómputo que calculen instrumentos financieros, elijan la mejor alternativa de inversión y determinen el costo o rendimiento efectivo.
- **Student Outcomes evaluados:**
  - ABET EAC 1: identificar, formular y resolver problemas complejos de ingeniería.
  - ABET CAC 1: analizar problemas complejos con computación, ciencia y matemática.
  - ICACIT A: aplicar matemáticas, ciencias e ingeniería.
  - ICACIT E: identificar, formular, buscar información y analizar.
  - ICACIT L: gestión en ingeniería y decisiones económicas.
- **Idioma:** todo el producto (interfaz, documentos, comentarios y mensajes) va en **español**.

## 2. Enunciado del trabajo final (resumen fiel)

Aplicación **web o móvil** para llevar el control permanente de la **cuenta corriente por créditos** que otorgan pequeños establecimientos (bodegas, panaderías, pollerías, peluquerías, spa, licorerías, etc.) a vecinos de su zona. Debe ser **genérica** y **multitienda**: varias tiendas de distintos giros en la misma plataforma. El enfoque es **el del comercio que da el crédito**, y el objetivo es **reemplazar el cuaderno de fiados**.

Requisitos funcionales:

1. El **administrador del sistema** da de alta o baja a una tienda con sus credenciales y datos. Cliente y administrador del negocio acceden con **usuario y clave**: el cliente solo consulta y el negocio administra.
2. El **administrador del negocio** da de alta o baja productos y servicios. Cada uno lleva proveedor (si aplica), marca, descripción, unidad de medida, **imagen**, **precio contado**, **precio de lista (crédito)** y si se puede vender en **un solo pago a fin de mes (fecha de corte)** o **en meses**.
3. El negocio da de alta o baja clientes con sus datos generales y, sobre todo:
   - la **tasa pactada (nominal o efectiva)**;
   - la **moneda**;
   - el **límite máximo de crédito** y el **máximo de meses**;
   - la **fecha de corte** y la **fecha de pago mensual**.
4. Los pagos en meses usan **obligatoriamente el método francés vencido simple ordinario** con meses de 30 días. Si la compra es anterior al corte, hay **gracia total** desde la compra hasta la fecha de pago y la deuda se capitaliza antes de calcular la cuota. Ejemplo: compra el 15/09, corte el 20/09, pago el 26 de cada mes → 11 días de gracia total y cuotas el 26/10, 26/11 y 26/12.
5. **Compras a fin de mes:**
   - Si se hacen antes de la fecha y hora de corte, pagan interés por los días entre la compra y la fecha de pago.
   - Si se paga tarde, se cobra además interés por los días de mora.
   - Una compra posterior al corte pasa al mes siguiente.
   - **No** se permiten compras que excedan el límite **ni pagos parciales**.
6. En la fecha de corte se genera el **listado de pago** de cada cliente: compras ordenadas por fecha e intereses acumulados hasta la fecha de pago. La **mora** va en un **ítem separado** ("intereses por mora"), calculada sobre el pago total que debió hacerse, por los días de atraso y con la tasa moratoria pactada (nominal o efectiva).

No es obligatorio llevar inventario ni stock, ni impuestos (IR, IGV).

### Anexo A — Convenciones de cálculo (obligatorias)

- **Año de 360 días**, mes comercial de **30 días**.
- Fórmula explícita de conversión entre tasa nominal y efectiva.
- **Prelación de pagos:** mora → interés compensatorio → capital.
- **Redondeo:** importes a **2 decimales**; tasas con **al menos 7 decimales**.
- Convenciones del curso:
  - Días exactos: sin contar el primer día y contando el último.
  - Una tasa nominal sin capitalización indicada se asume con capitalización **diaria**.
  - Una tasa sin periodo indicado se asume **anual**.

### Estructura del informe (enunciado)

1. Introducción
2. Índice
3. Student Outcome
4. Definiciones
5. Marco legal y teórico (todo concepto con su norma, bibliografía o fuente web)
6. Análisis y diseño:
   - a) Análisis de datos: entrada, salida e intermedios, con tipos, tamaños, formatos, valores por defecto y restricciones.
   - b) Diseño de la interfaz, con ayuda electrónica en cada campo.
   - c) Marco conceptual (fórmulas).
   - d) Al menos 2 juegos de datos de prueba.
7. Algoritmo (pseudocódigo, diagrama de flujo o Nassi-Schneiderman; no es un diagrama de procesos)
8. Modelo entidad-relación
9. **Sistema de información:** a) Conectividad, b) Base de datos, c) Código fuente, d) Ayuda y asistencia técnica, e) Validación y pruebas
10. **Uso de IA**
11. Anexos
12. Bibliografía

### Uso de IA (crítico)

Hay que detallar dónde participó la IA, **el porcentaje de apoyo**, la herramienta usada, el alumno que sirvió de puente, y **qué se pidió, qué se aceptó, qué se corrigió y por qué**. Si no se declara y el profesor la detecta, **todo el grupo recibe 00**.

**Toda ayuda de Claude o Claude Code (código, redacción y fuentes) debe registrarse en la tabla de la sección "Uso de inteligencia artificial" del informe.**

### Exposición

- El profesor puede descontar puntos si un integrante no sabe responder. **"En esa parte me ayudaron" no es válido.**
- El integrante ausente recibe 00.
- Vestimenta formal: terno y corbata o vestido formal.
- La puntualidad es estricta.

## 3. Hito 1 (semana 7) — entregado

- **Nota: 19.75 / 20.** Todos los criterios tuvieron puntaje completo excepto el marco teórico (0.75 / 1, "Buen nivel").
- **Observación del profesor:**
  > En el marco teórico faltó la problemática de estos negocios (MYPEs) respecto a la informalidad en el registro de sus créditos, el crédito comercial o fiado, el capital de trabajo inmovilizado, las cuentas por cobrar y la morosidad, con literatura o reportes que la respalden.

### Corrección aplicada (archivo `FiaFacil_Hito_1_Grupo06_corregido.docx`)

Se agregó el **apartado 2.6 "Problemática financiera de las MYPE que venden al crédito"**, con cinco subtítulos: informalidad y registro de los créditos; crédito comercial o fiado; cuentas por cobrar y capital de trabajo inmovilizado; morosidad; e implicancias para FíaFácil.

Datos usados (todos verificados en su fuente):

| Dato | Fuente |
|---|---|
| Informalidad MYPE de 86.5% en 2025 (83.8% en 2019); comercio 85.6% | ComexPerú, como se citó en Redacción Gestión, 2026 |
| Casi la mitad de las MIPYME sin crédito formal; falta de historial crediticio | OCDE, 2025 |
| Solo el 27.4% de las MIPYME accedió a crédito formal (diciembre de 2024) | PRODUCE, vía De la Vega Polanco, 2026 |
| Bodegas: 12% con crédito formal, 68% sin ningún crédito, 20% solo con crédito de proveedores a 1–2 semanas | Agremub, vía Montesinos Nolasco, 2026 |
| Morosidad de la cartera MYPE de 5.6% a marzo de 2026 | Universidad de Lima, 2026 |
| Crédito informal como atributo de las bodegas frente al retail moderno | Logiconsult, vía Canchari Reyes, 2026 |
| Literatura académica | Petersen y Rajan (1997); García-Teruel y Martínez-Solano (2007); Martínez Benavides (2021); Santos et al. (2025); Candello et al. (2015) |

Ajustes de coherencia hechos en el mismo documento:

- **Contenido:**
  - Introducción: remite al apartado 2.6.
  - Apartado 2.1: tema nuevo, criterio para cifras tomadas de prensa y fecha de consulta del 19/11/2026.
  - Anexo C: 11 filas nuevas.
  - Bibliografía: 11 referencias APA.
  - Student Outcome ICACIT E: menciona la literatura sobre el fiado y las MYPE.
- **Índice:** se renumeraron las páginas:

  | Sección | Página |
  |---|---|
  | Capítulo 3 | 14 |
  | 3.2 | 19 |
  | 3.3 | 24 |
  | 3.4 | 28 |
  | Capítulo 4 | 31 |
  | Capítulo 5 | 34 |
  | Uso de IA | 38 |
  | Anexos | 39 |
  | Anexo C | 40 |
  | Anexo D | 42 |
  | Bibliografía | 43 |

**Pendiente:** la tabla de aportes de la sección "Uso de inteligencia artificial" del informe sigue vacía. Debe completarse.

### Reglas de negocio del diseño (Hito 1, sección 3.1.1) — el código debe respetarlas

| Regla | Contenido |
|---|---|
| RN01 Separación | Cada operación se limita a la tienda y cuenta autorizadas; se valida en el servidor. |
| RN02 Moneda | Una cuenta tiene una sola moneda (PEN o USD). No hay tipo de cambio. |
| RN03 Corte | Compra con fecha y hora **menor** al corte → ciclo actual. Compra **igual o posterior** → ciclo siguiente. Zona horaria America/Lima. |
| RN04 Calendario | Corte entre los días 1 y 27; pago entre los días 2 y 28; el pago es posterior al corte. |
| RN05 Modalidades | Mensual = 1 obligación. Cuotas = n obligaciones francesas, con gracia hasta la fecha de pago del ciclo. |
| RN06 Crédito | Exposición = capital mensual pendiente + saldo de cuotas (con la gracia capitalizada). No incluye interés futuro. |
| RN07 Pago | Cancela íntegramente una obligación o un conjunto de ellas. Se rechazan los pagos parciales. |
| RN08 Mora | Base = total exigible vencido; días desde el vencimiento. Cargo separado, sin mora sobre mora. |
| RN09 Baja | Es lógica. Se conserva el historial. |
| RN10 Condiciones | Se versionan. Las compras previas conservan su versión. |
| RN11 Catálogo | Proveedor y marca son opcionales. Descripción, unidad, imagen, precios y modalidad son obligatorios. |
| RN12 Precisión | Importes con 2 decimales y HALF_UP; tasas con alta precisión; ajuste de la última cuota. |

### Fórmulas (Hito 1, capítulo 3)

| Concepto | Fórmula |
|---|---|
| Tasa efectiva para d días | `i(d) = (1 + i(p))^(d/p) − 1` |
| Tasa nominal para d días | `m = p/c ; i(d) = (1 + j/m)^(d/c) − 1` |
| Compra mensual | `I = R2(P × i(D(compra, vencimiento))) ; V = P + I` |
| Mora | `M = R2(V × iₘ(dₘ))`, con `dₘ = max(0, D(vencimiento, pago))` |
| Gracia total | `Pg = R2(P × (1 + TEM)^(g/30))`, con g = días hasta la fecha de pago del ciclo (G) |
| Cuota francesa | `C = R2(Pg × i / [1 − (1+i)^(−n)])`; si i = 0, `C = Pg/n` |
| Componentes de cada cuota | `Iₖ = R2(Sₖ₋₁ × i)`; la última cuota se ajusta para que el saldo quede en 0.00 |
| Crédito disponible | `Disponible = Límite − Exposición` |

### Juegos de prueba oficiales (sección 3.4) — no deben romperse

Condiciones comunes a ambos juegos: tienda T001, moneda PEN, límite S/ 1,000, máximo de 3 cuotas, corte el día 20 a las 20:00, pago el día 26, moratoria TEA 3%.

**Juego A** (TEA 24%, pago a fin de mes):

| Compra | Capital | Fecha de pago | Interés |
|---|---|---|---|
| 05/09/2026 10:00 | 120 | 26/09 | 1.52 (21 días) |
| 18/09/2026 10:00 | 80 | 26/09 | 0.38 (8 días) |
| 21/09/2026 10:00 | 50 | 26/10 | pasa al ciclo de octubre |

- Estado de septiembre: 200.00 + 1.90 = **201.90**.
- Pago el 01/10, con 5 días de atraso: mora **0.08**, total **201.98**.
- Un pago de S/ 150.00 se rechaza.
- Después del pago, el disponible es 950.00.

**Juego B** (TNA 24% con capitalización mensual):

- Compra de 600 el 15/09/2026, en 3 cuotas.
- TEM 0.02; TEA 0.268241794562545.
- 11 días de gracia; Pg = **604.37**; cuota = **209.57**.
- Cronograma:

  | Cuota | Interés | Saldo final |
  |---|---|---|
  | 1 | 12.09 | 406.89 |
  | 2 | 8.14 | 205.46 |
  | 3 | 4.11 | 0.00 |

- Intereses de las cuotas 24.34; total pagado **628.71**.
- Disponible: 395.63; después de la primera cuota, 593.11.

**Pruebas de frontera:**

| Caso | Resultado esperado |
|---|---|
| Compra a las 19:59:59 del día de corte | Paga el 26/09 |
| Compra a las 20:00:00 o 20:00:01 | Paga el 26/10 |
| Disponible de 100 | Se acepta una compra de 100 y se rechaza una de 100.01 |
| Tasa 0 | Cuotas de 200 |
| Pg 100, TEM 2%, 3 cuotas | Cuotas de 34.68, 34.68 y 34.67 |
| Vencimiento 26/10, pago 01/11 (6 días) | Mora 0.10 |

## 4. Hito 2 (semana 15) — en curso

### Entregables (anuncio del profesor, que prevalece sobre el enunciado)

1. **PowerPoint** con enfoque académico y comercial. Según el enunciado debe incluir: herramientas, lenguajes, base de datos, alojamiento, URL (si está desplegado) y **requisitos de hardware**.
2. **Informe final en PDF:** el Hito 1 corregido más el **punto 9 (a–e) desarrollado en detalle**.
3. **Directorio con todo el código fuente comprimido.**
4. El enunciado original también pide un **video demostrativo** de hasta 20 minutos, subido antes de la primera clase de la semana 15. Conviene tenerlo aunque el anuncio no lo mencione.

- **Nombre de archivo:** `6_TF` (formato "N° Grupo_TF").
- **Horario de exposición del Grupo 6:** **jueves de 13:15 a 13:45** (PDF de secuencia de exposiciones de la sección 7696).

### Secuencia obligatoria de la exposición (20 minutos + 5 de preguntas)

1. **Resumen ejecutivo del Hito 1 (unos 4 minutos):**
   - la problemática (usar el apartado 2.6);
   - acciones concretas por cada Student Outcome (ABET e ICACIT);
   - datos de entrada, salida e intermedios;
   - fórmulas, modelo entidad-relación y algoritmo general.
2. **Desarrollo del sistema (unos 4 minutos), en el orden del punto 9:**
   - a) Conectividad: arquitectura física y lógica, dónde está cada componente, cómo se comunican y cómo se protege el login.
   - b) Base de datos: motor, tablas y prueba de que todo el proceso financiero queda registrado.
   - c) Código fuente: lenguajes y frameworks; documentación técnica en el informe y código en el zip.
   - d) Ayuda: tooltips por campo, ayuda general y canal de soporte.
   - e) Validaciones y pruebas.
3. **Demo en vivo (unos 12 minutos), obligatoria:**
   - **registro de un usuario nuevo**;
   - **inicio de sesión** con ese usuario;
   - **proceso financiero completo** de principio a fin.

### Lo que las rúbricas piden para el nivel Sobresaliente (mostrarlo explícitamente)

- **ICACIT A, a.c2:** al menos **2 lenguajes de programación** (aquí: Python y JavaScript, más SQL), arquitectura de datos y arquitectura de red.
- **ICACIT A, a.c1, y ABET EAC 1.c3:** medir **esfuerzo, costo y tiempo** del proyecto.
- **ICACIT L:** proyecto definido con **PMBOK**, plan, seguimiento y decisiones económicas (cronograma, planificado frente a ejecutado, costo).
- **ICACIT E, e.c2 y e.c3:** **riesgos** documentados, plan de contingencia y fuentes que demuestren comprensión del problema.
- **ABET EAC 1.c2:** al menos **2 aportes científicos**, más métricas o indicadores (la literatura del apartado 2.6 sirve).
- **Logro del curso:** indicadores de costo o rendimiento efectivo y **proyección del flujo de caja**. El sistema ya tiene en el panel un flujo de cobranzas proyectado.

## 5. Arquitectura objetivo (lo que hay que construir)

**Stack:**

| Capa | Tecnología |
|---|---|
| Lenguaje | Python 3.11 o superior |
| Framework | Django 5.2 |
| Base de datos | PostgreSQL (probado con 16), vía psycopg 3 |
| Interfaz | Bootstrap 5.3 y Bootstrap Icons, locales en `static/vendor` |
| Navegador | JavaScript sin framework |
| Imágenes | Pillow |
| Configuración | python-dotenv |

Ejecución local (`runserver`). Base de datos PostgreSQL configurada con variables de entorno en `.env`.

### Estructura a crear

```
fiafacil/
├── config/            settings.py (lee .env), urls.py, formatos/ (punto decimal y fechas dd/mm/aaaa para es-PE)
├── cuentas/           Usuario (login por correo, UUID), Membresia (NEGOCIO|CLIENTE), registro, login,
│                      middleware TiendaActivaMiddleware, permisos.py (negocio_requerido, cliente_requerido, plataforma_requerida)
├── tiendas/           Tienda (PENDIENTE|ACTIVA|INACTIVA), Articulo; vistas de plataforma y catálogo
├── clientes/          CuentaCliente, CondicionCredito (versionada; tasas guardadas como decimal 0.24); API tasa equivalente
├── creditos/
│   ├── finanzas.py    MODELO MATEMÁTICO PURO (sin BD): Tasa, ciclo_de_compra, compra_mensual, capital_con_gracia,
│   │                  cuota_francesa, cronograma_frances, calcular_mora, r2, dias_exactos
│   ├── servicios.py   ALGORITMO (cap. 4) transaccional: exposicion, disponible, guardar_condicion, calcular_compra,
│   │                  registrar_compra, generar_estado, calcular_pago, registrar_pago, flujo_cobranzas
│   ├── models.py      Compra, DetalleCompra, Obligacion, EstadoCuenta, EstadoDetalle, Pago, PagoAplicacion
│   ├── views.py       Pantallas y API JSON (compras/simular/, clientes/<id>/pago/calcular/)
│   ├── tests.py       pruebas: juegos A y B, frontera, reglas, idempotencia, tienda ajena, registro y login
│   └── management/commands/generar_estados.py
├── core/              Auditoria, TopeTasa (topes BCRP), panel, portal del cliente, ayuda, admin.py (registro central,
│                      operaciones de solo lectura), templatetags/ff.py (campo con ⓘ, dinero, tasa), cargar_demo
├── templates/         base.html (barra lateral por rol), base_auth.html, parciales/campo.html, por app
├── static/            css/fiafacil.css, js/fiafacil.js, compra.js (simulación en vivo), pago.js, condicion.js
├── docs/              DOCUMENTACION_TECNICA.md (punto 9 a–e), GUION_DEMO.md (demo de 12 minutos)
├── README.md, requirements.txt, .env.example, docker-compose.yml (PostgreSQL opcional)
```

### Comandos que deben funcionar al terminar

```bash
pip install -r requirements.txt
cp .env.example .env                 # poner DB_PASSWORD
python manage.py migrate
python manage.py cargar_demo --con-operaciones   # sin el flag: datos limpios para hacer la demo desde cero
python manage.py runserver
python manage.py test                # todas las pruebas deben pasar
python manage.py generar_estados     # estados de los cortes ya cumplidos (para programarlo a diario)
```

El comando `cargar_demo` debe crear estos usuarios de demostración (clave `Fiafacil-2026`):

| Usuario | Perfil |
|---|---|
| `admin@fiafacil.pe` | Administrador de plataforma (is_staff) |
| `rosa@bodega.pe` | Negocio, tienda T001 "Bodega Doña Rosa" |
| `carmen@cliente.pe` | Cliente; portal de la cuenta C001 |

C001 corresponde al juego A y C002 al juego B. El artículo "Consumo general" vale S/ 1.00 por unidad, para reproducir los montos de los juegos.

### Flujo funcional que debe quedar funcionando

1. **Registro público.** Crea el usuario, la tienda en estado PENDIENTE y la membresía NEGOCIO. El administrador de la plataforma la activa en `/tiendas/plataforma/`.
2. **Negocio:** gestiona artículos (imagen obligatoria de máximo 2 MB), clientes con sus condiciones (las tasas se ingresan en %, por ejemplo 24) y el acceso del cliente.
3. **Nueva venta:** las líneas son dinámicas. El servidor simula la compra en vivo mostrando corte, vencimiento, días, tasa del periodo, interés o cronograma, y disponible. Al confirmar se registra con una clave de idempotencia.
4. **Estado de cuenta:** vista previa del ciclo y generación una vez cumplido el corte (`UNIQUE(cuenta, corte)`). La mora pagada o proyectada aparece como un ítem separado.
5. **Pago:** se seleccionan obligaciones y la fecha efectiva. El servidor calcula la mora y el total, y el importe debe ser exacto. Se aplica en orden mora → interés → capital y se emite un comprobante.
6. **Portal del cliente:** solo muestra sus propias cuentas (deuda, disponible, compras, estados y comprobantes).
7. **Panel del negocio:** indicadores (capital por cobrar, total con intereses, vencido, cobrado del mes), flujo de caja proyectado por mes, próximos vencimientos y obligaciones vencidas.
8. **Auditoría:** login, login fallido, registro, compras, pagos, condiciones, altas, bajas y accesos denegados.

### Ajustes aprobados el 20/11/2026 (tras revisar el enunciado, las rúbricas y el informe del Hito 1)

| Ajuste | Qué se construye | Fase | Impacto en el informe |
|---|---|---|---|
| A. Costo efectivo | `finanzas.py` calcula la **TCEA** de cada compra (TIR diaria de sus flujos, expresada en 360 días), sobre el precio de lista y sobre el **precio contado**. La simulación de la venta compara alternativas: contado, fin de mes y 1…n cuotas, con el total pagado y la TCEA. Campos `Compra.tcea` y `Compra.tcea_contado`. | 3, 4 y 6 | Reescribir el párrafo "Indicadores complementarios" del 3.3 (hoy dice que no se incorporan) citando la rúbrica del logro del curso; agregar la fórmula de la TCEA. Juego B: TCEA ≈ 0.2682737. |
| B. Indicadores de cartera | En el panel: índice de morosidad (vencido / cartera), periodo promedio de cobro y capital inmovilizado en cuentas por cobrar, conectados con el apartado 2.6. | 6 | Fórmulas de los indicadores en el capítulo 3. |
| C. Demo del ciclo completo | Quien se registra puede iniciar sesión con su tienda PENDIENTE (ve un aviso) y el administrador la activa desde otra ventana. La venta y el pago aceptan **fechas pasadas, nunca futuras** (para pasar fiados del cuaderno); la auditoría guarda la hora real del registro. | 4 y 5 | Tabla 3.1.2: estado de la tienda PENDIENTE, ACTIVA o INACTIVA (el informe dice BOOLEAN). |
| D. Ayuda con ejemplos | Cada `help_text` incluye un ejemplo de formato ("Ej.: 24 para 24 %"). | Todas | Sección 9d. |
| E. Evidencia de gestión | `docs/RIESGOS.md` con los riesgos que ocurrieron y su contingencia; script de respaldo `pg_dump` y políticas de red en la documentación técnica; medición de líneas de código y estimación COCOMO II al final. `git` local cuando esté instalado. | 2 y 9 | ICACIT A (a.c1, a.c2), E (e.c2, e.c3) y L. |

Decisiones de implementación de la fase 2 que deben reflejarse en el informe (capítulo 5):
- El saldo del plan en cuotas se deriva de las obligaciones (`Obligacion.saldo_final`); `Compra` no guarda un saldo propio.
- La pertenencia a la misma tienda se garantiza guardando `tienda` en Compra, Obligación, EstadoCuenta y Pago, y validándola en el servidor dentro de la transacción.
- `PagoAplicacion` tiene `UNIQUE(obligacion)`: una obligación solo puede cancelarse una vez.
- Los registros financieros heredan de `RegistroInmutable`: no se modifican ni se borran (solo `Obligacion.estado` y `pagada_en`, y `CondicionCredito.vigente_hasta`).

Reglas precisadas en la fase 4 (`creditos/servicios.py`); deben reflejarse en los capítulos 3 y 4 del informe:
- **Mora (RN08):** se calcula sobre el total que debió pagarse en cada vencimiento (obligaciones de la cuenta con el mismo vencimiento y la misma tasa moratoria): `M = R2(V_grupo × iₘ(d))`, y se reparte en proporción a cada obligación (la última absorbe los centavos). En los juegos A y B coincide con el cálculo por obligación (0.08 = 0.05 + 0.03).
- **Condición aplicable:** la versión vigente en la fecha de la compra (`condicion_en`). Una versión nueva no puede regir antes de la última compra.
- **Ciclo cerrado:** no se registran compras (por ejemplo, retroactivas) en un ciclo cuyo estado de cuenta ya se generó.
- **Orden de cuotas:** dentro de una compra, no se paga una cuota si queda pendiente una anterior.
- **Pago:** la fecha efectiva no puede ser futura ni anterior a la compra; el importe debe ser exactamente el total (se rechazan pagos parciales y montos mayores).
- **Exposición (RN06):** suma del capital de las obligaciones pendientes (en cuotas, las amortizaciones pendientes equivalen al saldo con la gracia capitalizada).
- Las pruebas están en `creditos/tests.py` (modelos), `creditos/test_finanzas.py` (modelo matemático) y `creditos/test_servicios.py` (servicios).

Completado el 25/11/2026 (cierre del sistema); debe reflejarse en el informe (capítulos 4 y 5):
- **Entidad 16, `Anulacion`:** corrección trazable de errores de registro (promesa de la sección 5.3). Venta: solo si ninguna obligación está pagada; sus obligaciones pasan a `ANULADA`. Pago: solo el último vigente de la cuenta (orden inverso); sus obligaciones vuelven a `PENDIENTE`. Siempre con motivo (mínimo 10 caracteres) y auditoría. `Compra.anulada`, `Pago.anulado` y `PagoAplicacion.anulada` son los únicos campos que cambian. La unicidad de la aplicación es `UNIQUE(obligacion) WHERE anulada = false`. Lo anulado no entra en estados, mora, exposición ni indicadores; un estado ya generado no se altera (la línea se marca).
- **Cambio de contraseña** del propio usuario (`/cuentas/clave/`), auditado (`CAMBIO_CLAVE`).
- **Tarea programada** de Windows «FiaFacil - generar estados» (`scripts/programar_tarea.ps1`, diaria a las 21:00, `StartWhenAvailable`), con registro en `logs/generar_estados.log`.
- **Topes del BCRP:** `python manage.py cargar_topes_bcrp` carga los de las notas oficiales del 01/04/2026 (mayo–octubre 2026: 114.13 % PEN, 99.84 % USD; copia en `docs/fuentes/`) y del 01/10/2026 (noviembre 2026 – abril 2027: 114.68 % PEN, 103.14 % USD), compensatorios. Sin tope moratorio (la nota no lo fija). Actualizar cada semestre; próxima actualización del BCRP: 01/05/2027.
- 176 pruebas; `creditos/test_anulacion.py` cubre la anulación.

## 6. Plan de construcción (en este orden)

Trabaja por fases. Al terminar cada una, ejecuta las pruebas y muestra al usuario lo que se hizo antes de continuar.

1. **Proyecto base:**
   - Django 5.2 con `requirements.txt`, `.env.example`, `.gitignore` y `docker-compose.yml` (PostgreSQL opcional).
   - Apps `cuentas`, `tiendas`, `clientes`, `creditos` y `core`.
   - `TIME_ZONE = "America/Lima"`, formatos peruanos con punto decimal y `AUTH_USER_MODEL = "cuentas.Usuario"`, con login por correo.
2. **Modelos de las 15 entidades del capítulo 5:**
   - Usuario, Membresía, Tienda, Artículo, CuentaCliente, CondiciónCrédito, Compra, DetalleCompra, Obligación, EstadoCuenta, EstadoDetalle, Pago, PagoAplicación, Auditoría y TopeTasa.
   - Restricciones `UNIQUE` y `CHECK` de la sección 5.3.
   - Importes en `NUMERIC(18,2)`; tasas guardadas como decimal (0.24).
   - Ejecutar `makemigrations` y `migrate` contra PostgreSQL.
3. **`creditos/finanzas.py`, sin base de datos:**
   - Implementar las fórmulas de la sección 3 de este archivo con `Decimal` (40 dígitos) y `r2()` HALF_UP.
   - **Criterio de aceptación:** las pruebas unitarias de los juegos A y B y de frontera (sección 3) dan exactamente los valores indicados.
4. **`creditos/servicios.py`, transaccional:**
   - Funciones: `exposicion`, `disponible`, `guardar_condicion` (versionado y tope del BCRP), `calcular_compra`, `registrar_compra`, `generar_estado`, `calcular_pago` y `registrar_pago` (prelación mora → interés → capital, sin pagos parciales).
   - Cada operación usa idempotencia por UUID, `select_for_update` y registro en auditoría.
   - **Criterio de aceptación:** pruebas de servicio de los juegos A y B (estado 201.90, pago 201.98, disponible 950.00; Pg 604.37, disponible 395.63 y luego 593.11), límite exacto, plazo excedido, fecha futura, cambio de tasa, idempotencia y acceso a tienda ajena (404).
5. **Autenticación y roles:**
   - Registro público: crea usuario, tienda PENDIENTE y membresía NEGOCIO.
   - Login y logout.
   - Middleware de tienda activa y decoradores `negocio_requerido`, `cliente_requerido` y `plataforma_requerida`.
   - Pantalla del administrador de plataforma para dar de alta o baja tiendas.
6. **Pantallas del negocio:**
   - Catálogo con imagen.
   - Clientes con condiciones (tasas ingresadas en %, con TEM y TEA equivalentes en vivo).
   - Nueva venta con simulación en vivo (API JSON + JavaScript) y detalle con cronograma.
   - Estados de cuenta (vista previa y generación al corte; mora como ítem separado).
   - Pagos con liquidación en vivo y comprobante.
   - Panel con indicadores y flujo de caja proyectado.
   - Auditoría.
7. **Portal del cliente:** solo sus cuentas, estados y comprobantes.
8. **Ayuda:**
   - `help_text` en cada campo, mostrado con un ícono ⓘ (tooltip) y el texto debajo.
   - Página `/ayuda/` con guía, preguntas frecuentes, fórmulas y perfiles.
   - Botón flotante de WhatsApp y correo de soporte configurables en `.env`.
9. **Datos de demostración y documentación:**
   - Comando `cargar_demo [--con-operaciones]` que reproduce los juegos A y B, y comando `generar_estados`.
   - `README.md` con la instalación paso a paso.
   - `docs/DOCUMENTACION_TECNICA.md` con el punto 9 (a–e).
   - `docs/GUION_DEMO.md` con la demo de 12 minutos.
10. **Verificación final:**
    - `python manage.py test` en verde.
    - Prueba manual del flujo completo: registro, alta de la tienda, login, artículo, cliente, venta mensual, venta en cuotas, intento de exceder el límite, estado y pago con mora.

Diseño visual libre, pero limpio y adaptable a celular (Bootstrap 5 guardado localmente en `static/vendor` para funcionar sin internet).

## 7. Reglas para Claude Code al trabajar en este repositorio

- **No cambies fórmulas ni redondeos** de `creditos/finanzas.py` sin justificarlo con el informe (capítulo 3) y sin mantener verdes los juegos A y B. Si una regla del enunciado obliga a cambiar el diseño, actualiza también el informe (capítulos 3 y 4) para que todo siga coherente.
- **Usa siempre `Decimal`**, nunca `float`, en cálculos financieros. Redondeo monetario con `r2()` (HALF_UP); tasas con 40 dígitos y mostradas con al menos 7 decimales (`formato_tasa`).
- **El cálculo financiero vive en el servidor.** El JavaScript solo muestra lo que devuelven las API.
- **Toda operación que escribe datos financieros** va en `transaction.atomic`, con `select_for_update` sobre la cuenta y una clave de idempotencia.
- **Nada financiero se edita ni se borra.** Las correcciones se hacen con nuevos registros o versiones (RN09 y RN10).
- **Filtra siempre por `request.tienda`** (RN01). El acceso ajeno devuelve 404 y se audita con `Auditoria.registrar`.
- **Cada campo nuevo lleva `help_text`**, porque es la ayuda por campo que exige la rúbrica, y se muestra con `{% campo form.x %}`.
- **Los mensajes al usuario** van en español, concretos, con la causa y el dato (por ejemplo, "Disponible: S/ X; se necesita: S/ Y").
- **Agrega pruebas en `creditos/tests.py`** para cada regla nueva y ejecuta `python manage.py test` antes de terminar.
- **Formato peruano:** punto decimal, fechas dd/mm/aaaa y zona America/Lima.
- **No inventes cifras ni fuentes** en documentos del informe. Toda referencia debe ser real y verificable, con formato APA 7 como el resto del informe.
- **Al corregir documentos por observaciones del profesor,** revisa todo el documento (índice, introducción, apartado 2.1, anexos y bibliografía) para que siga siendo coherente.
- **Niveles de riesgo** (si se piden en matrices): solo "Alto", "Medio" o "Bajo".
- **Recuerda al usuario** registrar en la sección de IA del informe lo que hagas en cada sesión: qué se pidió, qué se aceptó y qué se corrigió.

## 8. Pendientes del trabajo (fuera del código)

- [ ] Completar la tabla "Uso de inteligencia artificial" del informe: herramientas, porcentaje, alumno puente y qué se pidió, aceptó y corrigió (incluye el código generado con Claude Code y el apartado 2.6).
- [ ] Cuando el sistema esté construido: redactar el punto 9 (a–e) del informe a partir de `docs/DOCUMENTACION_TECNICA.md`, con capturas de pantalla y de las tablas en pgAdmin.
- [ ] Presentación PowerPoint con la secuencia obligatoria: tecnologías, requisitos de hardware y láminas de PMBOK, esfuerzo y costo, riesgos y aportes científicos.
- [ ] Video demostrativo de hasta 20 minutos.
- [ ] Ensayar la demo (`docs/GUION_DEMO.md`) y lograr que cada integrante pueda explicar `finanzas.py`, `servicios.py` y el modelo de datos.
- [ ] Opcional: desplegar en Render o Railway con PostgreSQL administrado y `DEBUG=False`, y agregar la URL a la presentación.
- [ ] Opcional: cargar los topes de tasas vigentes del BCRP en `/admin/` (TopeTasa) con su URL oficial; nunca inventar valores.
- [ ] Exportar el informe final a PDF y comprimir todo como `6_TF`.
