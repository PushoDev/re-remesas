# Re & Re — Remesas & Recargas

Plataforma web para **enviar remesas a Cuba** y **recargar móviles de ETECSA**, con
**membresía VIP** que mejora la tasa de cambio y da descuento en recargas. Prueba técnica
construida con **Django REST Framework** en el backend y **React + Vite + Tailwind** en el
frontend, como dos aplicaciones separadas.

La especificación completa está en
[`docs/Especificacion_Re_y_Re_Remesas_Recargas.pdf`](docs/Especificacion_Re_y_Re_Remesas_Recargas.pdf)
y las decisiones técnicas, con sus límites, en [`docs/DECISIONS.md`](docs/DECISIONS.md).

## Qué hace

| Historia | Qué incluye |
|---|---|
| **HU-AUTH-01** Registro y perfil | Registro con correo único, contraseña con letras y números, login con JWT, perfil Gratuita / VIP |
| **HU-MEM-01** Membresía VIP | Planes mensual y anual, pago por pasarela, activación solo cuando el pago se confirma |
| **HU-ADM-01** Tasas y márgenes | CRUD de tasas solo para administradores, margen distinto para VIP, historial |
| **HU-REM-01** Remesas | Calculadora en tiempo real, solicitud con ID de seguimiento (`RR-AAAAMMDD-XXXXX`), 7 medios de pago |
| **HU-REM-02** Verificación | Bandeja de administración con los 4 estados, revisión de comprobantes, aviso al cliente |
| **HU-TOP-01** Recargas ETECSA | Saldo y paquetes, promoción vigente detectada por el servidor, descuento VIP, orden Procesando / Exitosa / Fallida |

## Tecnología

| Capa | Tecnología |
|---|---|
| **Backend** | Python 3.12 · Django 6.1 · Django REST Framework 3.18 · SimpleJWT · django-cors-headers · django-environ |
| **Base de datos** | PostgreSQL (driver `psycopg2`) |
| **Frontend** | React 19 · TypeScript 6 · Vite 8 · Tailwind CSS 4 · React Router 7 · TanStack Query · React Hook Form + Zod · Axios |
| **Pruebas** | `pytest` + `pytest-django` (backend) · `vitest` (frontend) · `tsc` y `oxlint` (tipos y calidad) |

## Arquitectura

```text
djasoft-tecnico/
├── backend/                 Django + DRF (API JSON, nunca sirve HTML de negocio)
│   ├── config/              settings, urls
│   └── apps/
│       ├── users/           usuario (login por correo), perfil, autenticación
│       ├── memberships/     planes, suscripciones, activación del VIP
│       ├── payments/        capa de pagos: proveedores (simulado / manual), webhooks firmados
│       ├── exchange_rates/  tasas, márgenes, historial y el cálculo (único punto: convert())
│       ├── remittances/     remesas, ID de seguimiento, máquina de estados, comprobantes
│       ├── recharges/       paquetes, promociones, órdenes, proveedor de recargas
│       └── common/          validador de teléfono cubano, resumen del panel
├── frontend/                React (SPA)
│   └── src/                 pages · components · services · lib · hooks · schemas · types
└── docs/                    especificación y decisiones técnicas
```

Principios que gobiernan el código:

- **El backend manda.** El navegador nunca calcula importes: tasas, descuentos y totales los
  decide el servidor. Lo que se ve antes de confirmar es una cotización informativa.
- **Dinero siempre en `Decimal`**, nunca en `float`, con el redondeo documentado.
- **Instantánea.** Cada remesa y cada recarga guardan la tasa, el precio y el descuento usados:
  cambiar una tasa o un plan después no altera lo ya creado.
- **Proveedores externos detrás de una interfaz.** Pagos y ETECSA se atienden desde un único
  archivo de registro; sustituir uno por una integración real es cambiar una línea.
- **Sesión segura.** El token de acceso vive solo en memoria y el de renovación va en una cookie
  `httpOnly`. El frontend y la API se sirven desde el mismo origen (proxy de Vite).

## Requisitos

- **Python 3.12 o superior**
- **Node.js 22.12 o superior** (con `npm`)
- **PostgreSQL** accesible, con un usuario que pueda crear bases de datos (las pruebas crean
  una base temporal `test_<nombre>`)

## Puesta en marcha

### 1. Base de datos

Crea una base vacía (el nombre `re_re` es el que usa el ejemplo):

```bash
createdb -U postgres re_re
# o, desde psql:  CREATE DATABASE re_re;
```

### 2. Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate            # en Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env                # y ajusta DATABASE_URL a tu Postgres (ver "Variables de entorno")

python manage.py migrate            # crea las tablas
python manage.py seed_demo_data     # (opcional) usuarios, tasas, planes y paquetes de demostración
python manage.py runserver 8001     # la API queda en http://localhost:8001/api/
```

> El puerto **8001** es el que espera el proxy del frontend. Si usas otro, cambia
> `server.proxy['/api'].target` en `frontend/vite.config.ts`.

### 3. Frontend

En otra terminal:

```bash
cd frontend
npm install                         # o `npm ci` para instalar exactamente lo del lockfile
cp .env.example .env                # VITE_API_BASE_URL=/api (el valor por defecto sirve)
npm run dev                         # http://localhost:5173
```

Abre **http://localhost:5173**. Las llamadas a `/api` las reenvía Vite a Django, así que el
navegador solo habla con un origen y no hace falta configurar CORS ni cookies entre sitios.

### 4. Datos de demostración

`seed_demo_data` es **idempotente** (puedes ejecutarlo varias veces; restablece lo suyo y no
duplica nada) y carga todo lo necesario para recorrer la aplicación sin preparar nada a mano:

| Qué | Contenido |
|---|---|
| Usuarios | `admin@rere.test` (administrador) · `cliente@rere.test` (gratuito) · `vip@rere.test` (VIP, con suscripción real al plan mensual) · `vip.vencido@rere.test` (VIP caducado = gratuito) |
| Tasas | USD y EUR de ejemplo (no son tasas reales) |
| Planes | VIP Mensual y VIP Anual (precios de ejemplo) |
| Recargas | 6 paquetes de ejemplo y una promoción vigente |

La contraseña común de las cuentas de demostración la imprime el propio comando al terminar. En
`npm run dev`, la pantalla de login tiene además botones de **«Cuentas de prueba»** que rellenan
el formulario de cada rol.

> ⚠️ **Solo para desarrollo.** Los datos de demostración crean cuentas con una contraseña
> conocida, entre ellas un administrador. No los cargues en un entorno público.

Cada parte se puede cargar por separado: `seed_demo_users`, `seed_demo_rates`,
`seed_demo_plans` y `seed_demo_recharges`.

## Variables de entorno (`backend/.env`)

| Variable | Para qué | Por defecto en el ejemplo |
|---|---|---|
| `DATABASE_URL` | Conexión a Postgres: `postgres://usuario:clave@host:puerto/base` | `postgres://postgres:postgres@localhost:5432/re_re` |
| `DEBUG` | Modo desarrollo. **Debe ser `False` en producción** | `True` |
| `SECRET_KEY` | Clave secreta de Django. Cámbiala fuera de desarrollo | valor de desarrollo |
| `ALLOWED_HOSTS` | Hosts que Django acepta | `localhost,127.0.0.1,…` |
| `CORS_ALLOWED_ORIGINS` | Orígenes de navegador permitidos | `…,http://localhost:5173` |
| `CSRF_TRUSTED_ORIGINS` | Orígenes HTTPS de confianza | vacío / de ejemplo |
| `AUTH_COOKIE_SECURE` | Cookie del token de renovación solo por HTTPS. `False` en `http` local, `True` en producción | `False` |
| `PAYMENT_WEBHOOK_SECRET` | Firma HMAC de los webhooks de la pasarela simulada. Cámbialo fuera de desarrollo | valor de desarrollo |
| `PAYMENT_MOCK_ENABLED` | Habilita el checkout simulado. **Debe ser `False` en producción** | `True` |
| `REMITTANCE_MIN_AMOUNT` / `REMITTANCE_MAX_AMOUNT` | Límites por remesa en la moneda enviada (supuesto propio: la especificación no los define) | `1.00` / `10000.00` |

Frontend (`frontend/.env`): `VITE_API_BASE_URL` — por defecto `/api` (mismo origen vía proxy).

## Migraciones y comandos útiles

Todos desde `backend/` con el entorno virtual activo:

```bash
python manage.py migrate                      # aplica las migraciones pendientes
python manage.py showmigrations               # qué está aplicado y qué no
python manage.py makemigrations               # tras cambiar un modelo (genera la migración)
python manage.py makemigrations --check --dry-run   # falla si hay modelos sin migración
python manage.py createsuperuser              # un administrador propio, sin datos de demostración
python manage.py check                        # comprobación de configuración
```

El **admin de Django** está en `http://localhost:8001/admin/` (usuarios, planes, pagos y órdenes
de recarga). Ahí un administrador confirma o rechaza los pagos manuales (Zelle, Wise, efectivo).
El **panel de administración de la aplicación** está en `/admin` del frontend (remesas, recargas
y tasas de cambio) y solo lo ven los usuarios `is_staff`.

## Pruebas

```bash
# Backend (usa Postgres real; crea y borra su propia base de pruebas)
cd backend && source venv/bin/activate
pytest -q                                     # todas (tardan varios minutos)
pytest -q apps/recharges                      # una sola app

# Frontend
cd frontend
npm test                                      # vitest
npm run lint                                  # oxlint
npm run build                                 # tsc + vite build
```

## Cómo probar los flujos a mano

- **Remesa:** entra como `cliente@` o `vip@`, ve a *Enviar*, elige monto, destinatario y pago. Con
  `vip@` la calculadora muestra la tarifa preferencial. En un pago manual, sube un comprobante y
  confírmalo como `admin@` en *Administración → Remesas*.
- **Recarga:** *Recargas → Nueva recarga*. El resultado depende del **último dígito** del
  teléfono (regla del proveedor simulado): termina en `0` → Fallida, en `1` → Procesando, cualquier
  otro → Exitosa. La promoción vigente aparece sobre el paquete de 10 USD.
- **Pago en línea:** todos los medios en línea llevan a una pasarela **simulada** con «Pagar» y
  «Simular un pago fallido». No se cobra nada.

## Integraciones: qué es real y qué no

**No hay ninguna integración viva con pasarelas ni con ETECSA**, y la aplicación no lo finge.
Está todo detrás de interfaces para que cambiar una pieza sea una línea.

| Servicio | Estado | Detalle |
|---|---|---|
| Stripe, PayPal, Mercado Pago, EnZona | **Simulado** | Pasarela de la propia app; el webhook va firmado con HMAC-SHA256 y la verificación de la firma es real |
| Wise, Zelle, Efectivo | **Manual** | Se paga fuera de la app; un administrador verifica el comprobante y confirma |
| Recargas ETECSA | **Simulado** | No hay contrato ni credenciales; la respuesta depende del último dígito del teléfono |
| Tasas de cambio | **Propias** | Las define el administrador desde el panel; no se consulta una API externa |
| Correo / SMS | **No hay** | El aviso al cliente es por actualización periódica de la pantalla |

## API

Todas las rutas cuelgan de `/api/`. Salvo las marcadas como públicas, requieren sesión; las de
`admin/` solo las atienden usuarios `is_staff`.

| Grupo | Rutas |
|---|---|
| Salud | `GET health/` (pública) |
| Autenticación | `POST auth/register/` · `auth/login/` · `auth/refresh/` · `auth/logout/` · `GET users/me/` |
| Tasas | `GET exchange-rates/` (pública, según quién pregunta) · `admin/exchange-rates/` (+ `/<id>/`, `/<id>/history/`) |
| Membresía | `GET memberships/plans/` · `POST memberships/subscribe/` |
| Pagos | `GET payments/<ref>/` · `POST payments/webhooks/<proveedor>/` (firmado) · `POST payments/mock/<ref>/confirm/` (solo con `PAYMENT_MOCK_ENABLED`) |
| Remesas (cliente) | `POST remittances/quote/` (pública) · `GET, POST remittances/` · `GET remittances/<ID>/` · `POST remittances/<ID>/payment-proof/` |
| Remesas (admin) | `GET admin/overview/` · `GET admin/remittances/` · `…/<ID>/` · `PATCH …/<ID>/status/` · `GET …/<ID>/proof/` |
| Recargas (cliente) | `GET recharges/packages/` · `GET recharges/recent-contacts/` · `POST recharges/quote/` · `GET, POST recharges/` · `GET recharges/<uuid>/` |
| Recargas (admin) | `GET admin/recharges/` |

Los importes viajan como **cadenas decimales** (`"9.50"`), nunca como números de coma flotante.

## Decisiones y limitaciones conocidas

Las 39 decisiones están razonadas en [`docs/DECISIONS.md`](docs/DECISIONS.md). Las limitaciones que
conviene conocer:

- Los reembolsos (remesa cancelada tras pagarse, recarga fallida con pago cobrado) son **manuales**:
  la aplicación los marca, no los ejecuta.
- Una recarga en estado «Procesando» no se resuelve sola (el proveedor simulado no tiene consulta
  de estado ni webhook).
- En recargas solo se ofrecen pasarelas en línea; los pagos manuales exigen un comprobante que solo
  existe para remesas.
- Los comprobantes de pago no pasan por un antivirus y solo se conserva el último enviado.
- Sin correos ni SMS; el aviso al cliente es por actualización periódica.
- Las tasas, los planes y los paquetes de la demostración son **de ejemplo**, no una oferta real.
