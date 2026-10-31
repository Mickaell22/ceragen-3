# Ceragen 3.0

[![CI](https://github.com/Mickaell22/ceragen-3/actions/workflows/ci.yml/badge.svg)](https://github.com/Mickaell22/ceragen-3/actions/workflows/ci.yml)

Sistema de gestión para un centro de fisioterapia: pacientes, historial
clínico, paquetes de terapia, facturación y agenda de sesiones.

> En construcción. Avance y plan en [`docs/ROADMAP.md`](docs/ROADMAP.md).

## Stack

| Capa | Tecnología |
|---|---|
| Base de datos | PostgreSQL 17 (funciones `plpgsql`, `pgcrypto`, exclusion constraints) |
| API | Python, FastAPI, SQLAlchemy Core, Alembic |
| Frontend | React + TypeScript (Vite, Material UI) |
| Infra | Docker Compose, Railway |

## Correr en local

Requisitos: Docker con Compose.

```bash
cp .env.example .env    # completar los valores vacíos (openssl rand -hex 32)
docker compose up --build
```

`docker compose up` también corre el servicio `migrate`: crea los roles de la
base, aplica las migraciones de Alembic y crea el usuario administrador de la
demo (`SEED_ADMIN_*` en `.env`) antes de que arranque la API.

- Web: http://localhost:8080 (entra con `SEED_ADMIN_USERNAME` / `SEED_ADMIN_PASSWORD` de tu `.env`)
- API: http://localhost:8000 (documentación interactiva en `/docs`)
- Salud: http://localhost:8000/health

Endpoints de autenticación (documentados en `/docs`):

| Método | Ruta | Qué hace |
|---|---|---|
| `POST` | `/auth/login` | Usuario y contraseña → sesión en una cookie httpOnly (el token nunca llega a JavaScript). 401 si no coinciden, 423 si la cuenta está bloqueada. |
| `GET` | `/auth/me` | Perfil, roles y menús visibles del usuario de la sesión (el sidebar se arma con esto). |
| `POST` | `/auth/logout` | Revoca la sesión en la base y borra la cookie: el token deja de servir aunque no haya vencido. |

Gestión de usuarios (solo administradores; la base lo exige y la API responde 403):
`GET /users`, `GET /roles`, `POST /users`, `PUT /users/{id}`,
`POST /users/{id}/password`, `POST /users/{id}/unlock`.

Si algún puerto ya está ocupado en tu máquina, cámbialo en `.env`
(`POSTGRES_PORT`, `API_PORT`, `WEB_PORT`) y ajusta `CORS_ORIGINS` y
`VITE_API_URL` para que coincidan.

Front con recarga en caliente (contra la API de compose):

```bash
cd frontend && npm install && npm run dev
```

Tests de la base (permisos y auditoría, contra el Postgres de compose):

```bash
docker compose run --rm --build test
```

Nueva migración: `docker compose run --rm migrate alembic revision -m "descripcion"`
(el archivo aparece dentro del contenedor; más cómodo crearlo a mano en
`backend/migrations/versions/` siguiendo el formato de `0001_base.py`).

Lint (lo mismo que corre el CI en cada PR):

```bash
cd backend && ruff check . && ruff format --check .   # ruff fijado en requirements-dev.txt
cd frontend && npm run lint                            # oxlint
```

`VITE_API_URL` se incrusta al compilar: si la cambias, reconstruye con
`docker compose up --build web`.

## Decisiones de diseño

- **Integridad en la base:** reglas como "un terapeuta no puede tener dos
  sesiones que se pisen" las garantiza PostgreSQL, no solo la API.
- **Mínimo privilegio:** tres credenciales con usos separados. El superusuario
  solo crea los roles; `ceragen_owner` solo aplica migraciones; la API entra
  como `ceragen_app`, que no puede leer contraseñas, tocar la auditoría,
  borrar filas ni alterar el esquema.
- **Contraseñas fuera del alcance de la API:** bcrypt (pgcrypto) dentro de la
  base. La API no tiene permisos sobre las tablas de `security`; solo llama
  funciones como `security.fn_login`, que nunca devuelven el hash. Bloqueo
  temporal tras intentos fallidos y tiempo de respuesta parejo exista o no el
  usuario.
- **Tokens revocables y fuera del alcance de JavaScript:** el JWT viaja en una
  cookie httpOnly (un XSS no puede robarlo), lleva el id de la sesión (`jti`)
  y la API lo verifica contra la base en cada request; un logout o desactivar
  al usuario lo invalida al instante. Las escrituras con cookie exigen un
  `Origin` permitido (protección CSRF).
- **Errores sin fugas:** un error inesperado responde un mensaje genérico (el
  detalle va al log) y los errores de validación no repiten lo que se envió.
- **Auditoría automática:** un trigger genérico registra cada cambio en
  `audit.event` (jsonb antes/después y quién lo hizo); activarlo en una tabla
  nueva es `SELECT audit.fn_enable('schema.tabla')`.
- **Operaciones críticas atómicas:** facturar, pagar y agendar son funciones
  de base de datos transaccionales.

Detalle completo en [`docs/diseno-modelo.md`](docs/diseno-modelo.md).

## Créditos

La interfaz parte de [Modernize React Lite](https://github.com/adminmart/modernize-react-lite)
de AdminMart (licencia MIT, ver `frontend/LICENSE-modernize-lite.txt`),
portada a TypeScript y recortada a lo que usa el proyecto.

## Origen

Reescritura desde cero de un proyecto académico de la materia Desarrollo de
Aplicaciones Web II (Universidad de Guayaquil), aplicando buenas prácticas que
el original no tenía.
