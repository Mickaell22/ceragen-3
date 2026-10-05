# Roadmap — Ceragen 3.0

Cada "día" es una sesión de trabajo (2–4 h), no un día calendario. Cada día
termina en una rama mergeada a `main` con algo que funciona.

## Flujo de Git

**GitHub Flow** (simple, el estándar para un equipo chico o una persona):

- `main` siempre funciona y es lo que despliega Railway. Protegida: no se
  pushea directo, todo entra por Pull Request con el CI en verde.
- Una rama por tarea, corta (1–3 días como mucho), creada desde `main`:

  | Prefijo | Para | Ejemplo |
  |---|---|---|
  | `feat/` | funcionalidad nueva | `feat/db-billing-functions` |
  | `fix/` | corrección | `fix/api-login-lockout` |
  | `docs/` | documentación | `docs/model-design` |
  | `chore/` | mantenimiento, config | `chore/docker-compose` |
  | `test/` | solo tests | `test/billing-functions` |
  | `ci/` | pipelines | `ci/github-actions` |

- PR → revisión (el diff completo, aunque trabajes solo) → **squash merge** →
  se borra la rama. Un PR = un commit limpio en `main`.

No usamos GitFlow (`develop`, `release/*`, `hotfix/*`): sirve para productos
con versiones paralelas en producción. Aquí solo agrega pasos.

## Conventional Commits

Formato: `tipo(alcance): descripción en imperativo, minúscula, sin punto`

| Tipo | Cuándo |
|---|---|
| `feat` | funcionalidad nueva |
| `fix` | corrección de bug |
| `docs` | solo documentación |
| `refactor` | cambia código sin cambiar comportamiento |
| `test` | agrega o corrige tests |
| `chore` | tareas que no tocan código de la app (deps, config) |
| `ci` | pipelines |
| `build` | Docker, empaquetado |
| `perf` | mejora de rendimiento |

Alcances: `db`, `api`, `web`, `infra`, `docs`.

Ejemplos:

```
feat(db): add exclusion constraint to prevent overlapping sessions
fix(api): return 401 instead of 500 on expired token
docs: add data model design
chore(infra): add docker compose with postgres 17
feat(web)!: replace axios client with typed fetch wrapper
```

El `!` (o un pie `BREAKING CHANGE:`) marca un cambio incompatible.

## Fases y días

### Fase 1 — Modelo de datos
- [x] Día 0: dump limpio de respaldo + script de verificación (fuera del repo).
- [x] Día 1: diseño del modelo aprobado (`docs/diseno-modelo.md`) y repo creado.

### Fase 2 — Esqueleto del monorepo
- [x] Día 2: `chore/repo-setup` — `.gitignore`, `.env.example`,
      README mínimo, protección de `main`.
- [x] Día 3: `chore/docker-compose` + `feat/frontend-shell` — Postgres 17 +
      API FastAPI con healthcheck + front con Modernize Lite (MIT) portada a
      TypeScript, todo con `docker compose up`. (La Pro se descartó: su
      licencia no permite publicarla en un repo público.)
- [x] Día 4: `feat/db-migrations-base` — Alembic, roles `ceragen_owner` /
      `ceragen_app`, schemas, convenciones, trigger de auditoría genérico.
- [ ] Día 5: `ci/github-actions` — lint (ruff, eslint) + tests contra Postgres
      en cada PR.

### Fase 3 — Seguridad
- [ ] Día 6: `feat/db-security` — tablas `security`, `fn_login`, bcrypt con
      pgcrypto, bloqueo temporal, tests.
- [ ] Día 7: `feat/api-auth` — login JWT, dependencia `current_user`,
      `SET LOCAL app.user_id` por request, manejo de errores sin filtrar
      excepciones.
- [ ] Día 8: `feat/web-auth` — pantalla de login, cliente HTTP único con
      `VITE_API_URL`, rutas protegidas.
- [ ] Día 9: `feat/roles-menus` — roles, menús dinámicos por rol, sidebar.
- [ ] Día 10: `feat/users-admin` — gestión de usuarios y roles.

### Fase 4 — Módulos de negocio
- [ ] Día 11: `feat/catalogs` — impuestos, métodos de pago, tipos de terapia,
      género, estado civil (patrón CRUD que se repite después).
- [ ] Día 12: `feat/clinic-catalogs` — enfermedades, tipos, alergias.
- [ ] Día 13–14: `feat/persons-patients` — personas (validación de cédula),
      clientes, pacientes, alergias y enfermedades del paciente.
- [ ] Día 15: `feat/medical-history` — historial médico.
- [ ] Día 16: `feat/medical-staff` — personal médico.
- [ ] Día 17: `feat/products-promotions` — productos y promociones.
- [ ] Día 18–19: `feat/billing` — `fn_create_invoice`, `fn_register_payment`,
      `fn_void_invoice` + pantallas.
- [ ] Día 20–21: `feat/sessions` — agenda con exclusion constraint,
      reprogramar, completar, cancelar; vista de calendario.
- [ ] Día 22: `feat/reports` — dashboard (ingresos, sesiones, pacientes).

### Fase 5 — Calidad
- [ ] Día 23: `test/coverage` — completar tests de reglas críticas.
- [ ] Día 24: `docs/readme` — README con capturas, diagrama, decisiones.

### Fase 6 — Despliegue
- [ ] Día 25: `chore/railway` — servicios `api` y `web` desde el monorepo
      (Root Directory + Watch Paths), Postgres de Railway, variables.
- [ ] Día 26: verificación en producción, datos demo, link en el README.

Total estimado: ~26 sesiones. Se ajusta sobre la marcha.
