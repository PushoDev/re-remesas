# Re & Re — Remesas & Recargas

Prueba técnica: backend Django REST Framework + frontend React/Vite/Tailwind,
para una plataforma de remesas y recargas telefónicas (ETECSA) con membresías
VIP. Especificación completa en `Especificacion_Re_y_Re_Remesas_Recargas.pdf`
(fuera de este repo) y el resumen de alcance en `CONTEXT.md`.

## Arquitectura

```text
re-re/
├── backend/   Django + DRF + SimpleJWT + Postgres
├── frontend/  React + Vite + TypeScript + Tailwind
└── docs/DECISIONS.md    Decisiones técnicas (ADRs breves)
```

Backend y frontend son aplicaciones separadas que se comunican por HTTP/JSON.
Django nunca sirve HTML de negocio; React es la única interfaz de usuario.

## Requisitos

- Python 3.12+
- Node 22+
- Postgres accesible (local, contenedor propio, o el que ya tengas corriendo)

## Arranque rápido

```bash
# 1. Base de datos: crear una base Postgres vacía (ej. `re_re`) en tu
#    instancia de Postgres local y apuntar DATABASE_URL en backend/.env

# 2. Backend
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env           # ajustar si hace falta
python manage.py migrate
python manage.py runserver 0.0.0.0:8001

# 3. Frontend (otra terminal)
cd frontend
npm install
cp .env.example .env
npm run dev
```

Por defecto el frontend espera el API en `http://localhost:8001/api` (ver
`frontend/.env`). Si usás un proxy HTTPS local (nginx, Caddy, mkcert) con
dominios `.test`, ajustá `VITE_API_BASE_URL` y `ALLOWED_HOSTS`/
`CORS_ALLOWED_ORIGINS` del backend en consecuencia — ese paso es conveniencia
de desarrollo local y no forma parte del entregable.

## Tests

```bash
cd backend
source venv/bin/activate
pytest
```

## Estado

Ver `docs/DECISIONS.md` para decisiones de arquitectura y la bóveda de
Obsidian del autor para el backlog día a día. Este README se amplía en la
última etapa del desarrollo (documentación final).
