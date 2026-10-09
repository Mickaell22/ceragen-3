# Diseño del modelo de datos — Ceragen 3.0

Estado: **aprobado**. En implementación: base (schemas, roles, auditoría) en la
migración `0001`, `security` en la `0002`; el resto por módulos según `ROADMAP.md`.

Punto de partida: el esquema `ceragen` del proyecto original (36 tablas, 41 FK,
6 UNIQUE, 25 triggers), limpiado de restos de otras prácticas. Este documento
dice qué se conserva, qué cambia y por qué.

## 1. Principios

1. **Integridad en la base, no solo en la API.** Lo que nunca debe pasar
   (montos negativos, citas que se pisan, cédulas inválidas) lo rechaza
   Postgres con `CHECK`, `UNIQUE` y `EXCLUDE`, aunque alguien se salte la API.
2. **Híbrido.** CRUD simple de una tabla desde Python (SQLAlchemy Core, SQL
   explícito). Operaciones transaccionales o críticas como funciones
   `plpgsql`. Cada consulta vive en un solo lugar (DRY).
3. **Mínimo privilegio.** La API se conecta con un rol que no puede leer
   contraseñas, escribir la auditoría, borrar filas ni alterar el esquema.
4. **Borrado lógico.** Nada se elimina físicamente; `state = false` +
   `deleted_at`/`deleted_by`.
5. **Todo versionado.** Tablas, funciones, triggers y permisos salen de
   migraciones Alembic. La base se recrea desde cero con un comando.

## 2. Organización: un schema por módulo

Hoy todo vive en `ceragen` con prefijos en el nombre de la tabla
(`segu_`, `admin_`, `clinic_`, `audi_`). Propuesta: **un schema de Postgres por
módulo** y nombres sin prefijo.

| Schema | Contenido |
|---|---|
| `security` | usuarios, roles, módulos, menús, sesiones de login |
| `core` | personas, clientes, catálogos generales, parámetros |
| `clinic` | pacientes, personal médico, historial, catálogos clínicos, citas |
| `billing` | productos, promociones, impuestos, facturas, pagos, gastos |
| `audit` | registro de eventos |

Por qué: los permisos se dan por schema (`GRANT ... ON ALL TABLES IN SCHEMA
billing`), así la matriz de privilegios queda en pocas líneas y es fácil de
auditar. Además el modelo se lee solo.

## 3. Convenciones (aplican a todas las tablas)

| Hoy | 3.0 | Motivo |
|---|---|---|
| Prefijo por columna (`pat_id`, `cli_name`, `inv_date`) y a veces sin prefijo (`id`, `state`) | Sin prefijo: `id`, `name`, `created_at`; FK como `<entidad>_id` | Hoy es inconsistente (`segu_user_rol.id_user` vs `admin_client.cli_person_id`) |
| `serial` + secuencias sueltas | `bigint GENERATED ALWAYS AS IDENTITY` | Estándar SQL, sin secuencias huérfanas |
| `timestamp without time zone` | `timestamptz` | Evita líos de zona horaria entre Railway (UTC) y Ecuador |
| Fechas puras guardadas como timestamp (`per_birth_date`) | `date` | Una fecha de nacimiento no tiene hora |
| `user_created varchar(100)` (login como texto) | `created_by bigint` FK a `security.user` | Hoy no hay integridad: se puede auditar a un usuario que no existe |
| `date_created NOT NULL` sin default | `created_at timestamptz NOT NULL DEFAULT now()` | La API ya no tiene que mandarlo |
| `*_state boolean` | `is_active boolean NOT NULL DEFAULT true` | Un solo nombre en todo el modelo |
| Typos (`genre`, `aut_table_descriptiom`, `pme_require_picture_proff`) | `gender`, etc. | — |
| FK sin índice (hoy hay 0 índices) | Índice en cada FK y en columnas de búsqueda | Postgres no indexa las FK solo |

Columnas comunes de auditoría en cada tabla de negocio:
`created_at, created_by, updated_at, updated_by, deleted_at, deleted_by, is_active`.

## 4. Cambios por módulo

### 4.1 security

| Tabla | Cambio |
|---|---|
| `user` | `password` deja de ser MD5: **bcrypt vía `pgcrypto`** (`crypt(p, gen_salt('bf', 12))`). La API nunca lee el hash: `fn_login` compara dentro de la base. Se elimina `twofa_enabled` (no hay 2FA; YAGNI). `login_attempts` + `locked_until` para bloqueo temporal en vez de bloqueo permanente. |
| `role` | Se conserva `is_admin`. |
| `user_role` | Hoy `state` es nullable: `NOT NULL`. `UNIQUE (user_id, role_id)`. |
| `module`, `menu`, `menu_role` | `menu` tiene `href`, `url` y `key` que se repiten: queda solo `path` + `icon`. `UNIQUE (menu_id, role_id)`. |
| `login` → `session` | Hoy guarda el JWT completo (`varchar(1000)`). Se guarda solo el `jti` (id del token) y la IP, para poder revocar sesiones sin almacenar tokens. |
| `user_notification` | **Fuera del MVP.** Existe en el esquema pero nunca se usó. |

### 4.2 core

| Tabla | Cambio |
|---|---|
| `person` | `identification` con `CHECK (core.fn_is_valid_cedula(...))` cuando el tipo es cédula ecuatoriana (algoritmo módulo 10). Se agrega `identification_type` (cédula / RUC / pasaporte), porque hoy un pasaporte rompería la validación. `birth_date date`. |
| `gender`, `marital_status` | Catálogos simples, se conservan. |
| `client` | Es quien **paga** (puede ser distinto del paciente: un padre que paga la terapia del hijo). `identification` con la misma validación. |
| `parameter` (hoy `admin_parameter_list`) | Se conserva como tabla clave/valor de configuración del negocio. |

### 4.3 clinic

| Tabla | Cambio |
|---|---|
| `patient` | Se eliminan `pat_allergies`, `pat_medical_conditions` (texto libre) porque **duplican** `patient_allergy` y `patient_disease`. `blood_type` pasa a `CHECK (blood_type IN ('A+','A-','B+','B-','AB+','AB-','O+','O-'))`. `client_id` pasa a nullable (un paciente puede pagarse solo). |
| `medical_staff`, `medical_staff_type` | Se conservan. |
| `medical_history` | Se conserva. |
| `disease_type`, `disease`, `allergy`, `patient_disease`, `patient_allergy` | Se conservan; `UNIQUE (patient_id, allergy_id)` y `UNIQUE (patient_id, disease_id)`. |
| `therapy_session` (hoy `clinic_session_control`) | Ver 4.5: es el cambio más importante. |

### 4.4 billing

| Tabla | Cambio |
|---|---|
| `invoice` | **Bug del original:** `inv_client_id` apunta a `admin_person` aunque existe `admin_client`. Pasa a FK a `core.client`. Se agrega `status` (`issued`, `paid`, `void`). `number` lo genera `fn_create_invoice` con una secuencia, no la API. Se conserva `grand_total` como columna `GENERATED`. `CHECK (subtotal >= 0 AND discount >= 0 AND discount <= subtotal)`. |
| `invoice_detail` | `CHECK (quantity > 0 AND unit_price >= 0)`. |
| `invoice_tax` | Se conserva; `invoice.tax` se calcula desde aquí dentro de la función (hoy hay dos fuentes de verdad). |
| `invoice_payment` | `CHECK (amount > 0)`. La función valida que la suma de pagos no supere el total y que se envíe referencia/comprobante si el método lo exige. |
| `payment_method`, `tax` | `CHECK (percentage BETWEEN 0 AND 100)`. |
| `product` | Un producto es un **paquete de N sesiones** de un tipo de terapia. `CHECK (price >= 0 AND total_sessions > 0)`. |
| `promotion` | `CHECK (end_date >= start_date AND discount_percent BETWEEN 0 AND 100)`. |
| `expense`, `expense_type` | **Fuera del MVP** (nunca tuvo pantalla). Candidato para el dashboard de ingresos vs. gastos. |

### 4.5 Citas: `clinic.therapy_session`

Flujo de negocio: el paciente compra un producto (ej. "10 sesiones de
fisioterapia") → se emite la factura → **la función crea las 10 sesiones
pendientes** → se van agendando una por una.

Cambios respecto al original:

- `sec_ses_agend_date` (solo inicio) pasa a `scheduled_at tstzrange` (inicio y
  fin). Sin fin no se puede detectar un choque.
- `ses_consumed` + `ses_state` (dos booleanos que podían contradecirse) pasan a
  `status`: `pending` → `scheduled` → `completed` / `cancelled` / `no_show`.
- **Exclusion constraint:** un terapeuta no puede tener dos sesiones que se
  solapen.

  ```sql
  CREATE EXTENSION IF NOT EXISTS btree_gist;
  ALTER TABLE clinic.therapy_session ADD CONSTRAINT no_overlap_staff
    EXCLUDE USING gist (medical_staff_id WITH =, scheduled_at WITH &&)
    WHERE (status IN ('scheduled', 'completed'));
  ```

  La base rechaza el choque aunque dos personas agenden al mismo tiempo. El
  original intentaba validarlo en Python y el chequeo nunca funcionaba
  (siempre leía 0).
- Lo mismo por paciente: un paciente no puede estar en dos sesiones a la vez.
- `sec_typ_id` se elimina: el tipo de terapia ya viene del producto.

### 4.6 audit

- Un **solo trigger genérico** `audit.fn_log_change()` en todas las tablas de
  negocio. Hoy solo 13 tablas están auditadas y justo las importantes
  (facturas, pagos, pacientes, citas) **no**.
- `old_data` / `new_data` como `jsonb`. Hoy son `varchar(1000)` y se truncan.
- El usuario responsable sale de una variable de sesión que la API fija en
  cada transacción (`SET LOCAL app.user_id = ...`), no de buscar el login
  como texto.
- Se elimina `audi_tables`: el trigger guarda el nombre de la tabla
  (`TG_TABLE_SCHEMA.TG_TABLE_NAME`).

## 5. Funciones de base de datos

| Función | Hace |
|---|---|
| `security.fn_login(login, password)` | Valida bcrypt, bloqueo temporal, registra intento. Devuelve usuario y roles, nunca el hash. |
| `security.fn_create_user(...)`, `fn_change_password(...)` | Hashean dentro de la base. |
| `security.fn_menus_for_user(user_id, role_id)` | Árbol de menús del rol activo. |
| `core.fn_is_valid_cedula(text)` | Validación módulo 10; `IMMUTABLE`, usable en `CHECK`. |
| `billing.fn_create_invoice(client_id, patient_id, items jsonb, ...)` | Factura + detalles + impuestos + sesiones pendientes, en una transacción. |
| `billing.fn_register_payment(invoice_id, method_id, amount, ...)` | Valida saldo y requisitos del método; marca `paid` al completar. |
| `billing.fn_void_invoice(invoice_id, reason)` | Anula y cancela las sesiones no ejecutadas. |
| `clinic.fn_schedule_session(session_id, staff_id, start, duration)` | Agenda; el `EXCLUDE` garantiza que no haya choques. |
| `clinic.fn_reschedule_session`, `fn_complete_session`, `fn_cancel_session` | Transiciones de estado válidas, nada más. |
| `billing.fn_income_report(from, to)`, `clinic.fn_therapy_report(...)` | Reportes. |
| `audit.fn_log_change()` | Trigger genérico. |

Cada función tiene su test en pytest contra un Postgres real.

### Notas de implementación de `security` (día 6)

- `fn_login` **no lanza excepciones**: devuelve `status` (`ok`, `invalid`,
  `locked`). Un `RAISE` revertiría el contador de intentos fallidos. La
  política (intentos máximos, minutos de bloqueo, duración de sesión) llega
  como parámetro desde la configuración de la API.
- Usuario inexistente o inactivo: `invalid`, y se calcula igual un bcrypt
  para que el tiempo de respuesta no revele si existe. `locked` sí revela que
  la cuenta existe (fuga aceptada a cambio de explicarle al usuario por qué
  no entra); mientras dura el bloqueo no se verifica la contraseña.
- `fn_session_user(jti)` se consulta en cada request: un JWT vigente no sirve
  si la sesión fue revocada o el usuario desactivado.
- `fn_create_user` exige que el usuario de la transacción sea admin, salvo
  que la sesión sea `ceragen_owner` (migraciones y semilla).
- `fn_change_password` cierra todas las sesiones abiertas del usuario.
- El trigger de auditoría descarta la columna `password_hash`.
- Columnas de auditoría y triggers comunes en `migrations/conventions.py`:
  `created_by` se llena solo desde `app.user_id` y `core.fn_touch()` mantiene
  `updated_at`/`updated_by`.
- Pospuesto: `person_id` en `security.user` (llega con `core`) y `module`,
  `menu`, `menu_role` (día 9, cuando el front los consuma).

## 6. Roles y permisos

| Rol | Uso |
|---|---|
| `ceragen_owner` | Dueño de tablas y funciones. Lo usan **solo** las migraciones. |
| `ceragen_app` | La API. |

`ceragen_app`:

| Objeto | Permiso |
|---|---|
| `core`, `clinic` (salvo citas), catálogos de `billing` | `SELECT, INSERT, UPDATE` |
| `security.*` | Ninguno directo. Solo `EXECUTE` sobre sus funciones. |
| `billing.invoice*`, `clinic.therapy_session` | `SELECT`. La escritura solo por funciones. |
| `audit.*` | Ninguno. |
| Cualquier tabla | Sin `DELETE`, sin `TRUNCATE`, sin DDL. |

Las funciones que escriben donde la API no puede usan `SECURITY DEFINER` con
`SET search_path` fijo (sin eso, `SECURITY DEFINER` es un hueco de seguridad).

Cómo se aplica (implementado en el día 4):

- **Los roles los crea un bootstrap** (`backend/app/db/bootstrap.py`) con el
  superusuario, porque son objetos del cluster y Alembic corre como
  `ceragen_owner`. Es idempotente y resincroniza las contraseñas con el
  entorno (permite rotarlas). Deja a `ceragen_owner` como dueño de la base
  y quita `CONNECT` a `PUBLIC`.
- **Nada es ejecutable por defecto:** Postgres da `EXECUTE` a `PUBLIC` en cada
  función nueva; la migración base lo revoca con `ALTER DEFAULT PRIVILEGES`.
  Cada función que la API pueda llamar se concede a mano en su migración.
- **Permisos de tabla explícitos:** no hay default privileges de tablas para
  `ceragen_app`; cada migración concede lo justo sobre lo que crea. Olvidarse
  un `GRANT` falla cerrado (la API recibe "permission denied"), nunca abierto.
- **Techo conocido:** `ceragen_app` todavía puede conectarse a la base de
  mantenimiento `postgres` (CONNECT de `PUBLIC` por defecto), sin poder crear
  nada ahí. No se toca porque en Railway es la base del proveedor.

## 7. Datos semilla

- **Repo público:** solo datos ficticios (personas inventadas con cédulas
  válidas generadas, catálogos reales como impuestos del SRI y tipos de
  terapia). Usuario demo `admin` con contraseña desde `.env`.
- **Respaldo con datos de prueba del curso:** `backups/ceragen_clean.sql`,
  fuera del repo.

## 8. Fuera del MVP (anotado para después)

Notificaciones entre usuarios, gastos, 2FA, tipo de sangre como tabla,
consentimiento informado, subida de comprobantes a almacenamiento externo.

## 9. Decisiones tomadas

1. **Un schema por módulo** (`security`, `core`, `clinic`, `billing`,
   `audit`), sin prefijos en los nombres de tabla.
2. **Nombres en inglés** en tablas, columnas y funciones.
3. **Hash con `pgcrypto` (bcrypt) dentro de la base.** La API nunca lee el
   hash, coherente con el mínimo privilegio. Se descartó argon2 en Python
   porque obligaba a dar a la API lectura sobre la columna de contraseñas.
