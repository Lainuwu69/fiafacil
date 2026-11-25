# Registro de riesgos — FíaFácil (Grupo 6)

Insumo para las rúbricas ICACIT E (e.c2: riesgos documentados; e.c3: planes de
contingencia ejecutados) e ICACIT L (seguimiento del proyecto).

Niveles: **Alto**, **Medio** o **Bajo**. Estado: Abierto, Mitigado, Materializado
(contingencia ejecutada) o Cerrado.

## Riesgos identificados

| ID | Riesgo | Probabilidad | Impacto | Respuesta planificada | Estado |
|---|---|---|---|---|---|
| R01 | Incompatibilidad de librerías con la versión de Python instalada | Media | Alto | Usar una versión de Python con soporte oficial de Django, psycopg y Pillow | **Materializado** (ver M01) |
| R02 | Falta de software base (PostgreSQL, git) en las máquinas del grupo | Alta | Alto | Instalación guiada con winget; alternativa con Docker (`docker-compose.yml`) | **Materializado** (ver M02) |
| R03 | Error en la hora de corte por zona horaria (compras a las 20:00 asignadas al ciclo equivocado) | Media | Alto | `TIME_ZONE = America/Lima`, campos `timestamptz` y pruebas de frontera 19:59:59 / 20:00:00 / 20:00:01 | **Materializado y corregido** (ver M03) |
| R04 | Diferencias de centavos frente a los juegos A y B por usar `float` | Media | Alto | `Decimal` con 40 dígitos, `NUMERIC` en la base y redondeo HALF_UP; pruebas automáticas con los valores exactos | Mitigado |
| R05 | Doble registro de una venta o un pago (doble clic, red lenta) | Media | Alto | Clave de idempotencia `UNIQUE(tienda, clave)` y `UNIQUE(obligacion)` en las aplicaciones de pago | Mitigado (fase 2) |
| R06 | Que una tienda vea datos de otra | Baja | Alto | Filtro obligatorio por tienda en el servidor, error 404 y auditoría del intento | Mitigado (pruebas automáticas y verificación manual del 20/11/2026) |
| R07 | Falla del equipo o de internet el día de la exposición | Media | Alto | Ejecución 100 % local, Bootstrap guardado en `static/vendor`, video de respaldo, datos de demostración con `cargar_demo` y plan B en `docs/GUION_DEMO.md` | **Materializado y resuelto** (ver M04) |
| R08 | Pérdida de la base de datos | Baja | Alto | Respaldo con `scripts/respaldo.ps1` (`pg_dump`) antes de la demo y a diario; restauración con `pg_restore` | Mitigado (probado el 20/11/2026: 86.7 KB) |
| R09 | Un integrante no sabe explicar parte del código en la exposición | Media | Alto | Explicación en lenguaje sencillo al cierre de cada fase y ensayo con `docs/GUION_DEMO.md` | Abierto |
| R10 | Uso de IA no declarado (nota 00 para todo el grupo) | Baja | Alto | `docs/REGISTRO_IA.md` actualizado al cierre de cada fase | Mitigado |
| R11 | Contradicción entre el código y el informe del Hito 1 | Media | Medio | Los cambios de diseño se anotan en `CLAUDE.md` (ajustes aprobados) para trasladarlos al informe | Abierto |
| R12 | Datos de prueba mezclados con los de la demo (por ejemplo, otra tienda con el código T001) | Alta | Medio | `cargar_demo --reiniciar --si` deja la base limpia antes de la exposición | Mitigado (fase 9) |
| R13 | El día de la exposición falta tiempo para la demo de 12 minutos | Media | Alto | Guion cronometrado con datos exactos (`docs/GUION_DEMO.md`) y ensayo previo | Abierto |
| R14 | Con `DEBUG=True`, un error 404 o 500 muestra la página técnica de Django (rutas y detalles internos) | Media | Medio | En la demo local es aceptable; en un despliegue se usa `DEBUG=False`, que muestra las páginas propias `404.html` y `403.html` | Abierto (decisión de despliegue) |
| R15 | Tabla de topes del BCRP vacía o desactualizada: la validación de tasas máximas no actúa | Media | Medio | `cargar_topes_bcrp` con la nota informativa oficial del BCRP (el grupo aportó el documento, porque el sitio bloquea la descarga automática); actualizar cada semestre | Mitigado (25/11/2026: mayo–octubre 2026 y noviembre 2026 – abril 2027 desde las notas oficiales). Falta el tope moratorio, que las notas no fijan |
| R16 | Un error de registro (venta o pago) no se puede corregir sin borrar datos | Media | Alto | Anulación trazable con motivo (tabla `anulacion`), sin borrar nada (RN09) | Mitigado (25/11/2026) |

## Contingencias ejecutadas

| ID | Fecha | Riesgo | Qué pasó | Contingencia aplicada | Resultado |
|---|---|---|---|---|---|
| M01 | 19/11/2026 | R01 | La máquina tenía Python 3.15.1, para el que Django 5.2, psycopg 3 y Pillow aún no declaran soporte oficial. | Se instaló Python 3.13.17 junto a la 3.15 y el entorno virtual se creó con `py -3.13`. | Instalación de dependencias sin errores. |
| M02 | 19/11/2026 | R02 | PostgreSQL y Docker no estaban instalados. El 20/11/2026 se detectó que tampoco hay `git`. | PostgreSQL 16.16 instalado con winget (con pgAdmin 4). `git` queda pendiente; mientras tanto, las fechas de `REGISTRO_IA.md` sirven de evidencia de seguimiento. | Base `fiafacil` creada y operativa. |
| M03 | 20/11/2026 | R03 | La prueba automática de zona horaria falló: se había forzado la sesión de PostgreSQL a hora de Lima, pero Django trabaja la sesión en UTC a propósito. | Se quitó la configuración y la prueba pasó a verificar que una hora de Lima (20:00 del corte) se guarda y se recupera sin cambios. | 10/10 pruebas en verde. |
| M04 | 21/11/2026 | R07, R08 | Una falla de la laptop obligó a usar «Restaurar sistema» de Windows, que la devolvió al 19/11/2026 23:41. Los archivos del proyecto no se afectaron, pero se borraron los programas de PostgreSQL 16, instalado minutos después de ese punto: carpeta `bin` vacía y sin servicio. La carpeta de datos sí se conservó. | (1) Diagnóstico: se revisaron los archivos, Python 3.13, el entorno virtual y PostgreSQL. (2) Copia de la carpeta de datos (66 MB) a `C:\Users\user\respaldo_postgres16_data_20261121`. (3) Reinstalación de PostgreSQL 16.16 con winget, reutilizando la carpeta de datos y la misma contraseña. (4) Verificación: conexión, migraciones y 159 pruebas. Además estaban disponibles los respaldos `pg_dump` de `respaldos/` y `cargar_demo`. | Base `fiafacil` recuperada íntegra (24 tablas, T001 y usuarios de la demo); 159/159 pruebas en verde; sin pérdida de código ni de datos. **Lección:** crear un punto de restauración de Windows después de instalar el software del proyecto y respaldar la base antes de cambios en el equipo. **Aplicada el 21/11/2026:** respaldo `fiafacil_20261121_2325.dump` y punto de restauración manual «FíaFácil con PostgreSQL 16» (el creado por comando se omitió por el límite de Windows de uno cada 24 horas). |
