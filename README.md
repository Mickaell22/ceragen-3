# Ceragen 3.0

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

- Web: http://localhost:8080
- API: http://localhost:8000 (documentación interactiva en `/docs`)
- Salud: http://localhost:8000/health

Si algún puerto ya está ocupado en tu máquina, cámbialo en `.env`
(`POSTGRES_PORT`, `API_PORT`, `WEB_PORT`) y ajusta `CORS_ORIGINS` y
`VITE_API_URL` para que coincidan.

Front con recarga en caliente (contra la API de compose):

```bash
cd frontend && npm install && npm run dev
```

`VITE_API_URL` se incrusta al compilar: si la cambias, reconstruye con
`docker compose up --build web`.

## Decisiones de diseño

- **Integridad en la base:** reglas como "un terapeuta no puede tener dos
  sesiones que se pisen" las garantiza PostgreSQL, no solo la API.
- **Mínimo privilegio:** la API se conecta con un rol que no puede leer
  contraseñas, escribir la auditoría ni borrar filas.
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
