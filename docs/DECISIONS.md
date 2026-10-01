# Decisiones técnicas — Re & Re

## 1. Frontend y backend separados

React (Vite) consume la API de DRF por HTTP/JSON. Django no sirve plantillas
de negocio. Esto permite que las validaciones monetarias vivan solo en el
backend (nunca confiar en cálculos del cliente) y mantiene el contrato de API
explícito.

## 2. Postgres: instancia local propia del desarrollador, no contenedor por proyecto

El backend se conecta por `DATABASE_URL` (`backend/.env`, no versionado) a
cualquier Postgres accesible — en desarrollo, una base dedicada (`re_re`)
dentro de la instancia de Postgres que ya corre en la máquina del autor. No
se incluye un `docker-compose.yml` de proyecto: levantar la base queda a
criterio de quien corra el proyecto (contenedor propio, instalación local,
etc.), documentado en el README. El proxy HTTPS con dominios `.test` usado
durante el desarrollo es una comodidad local y no se documenta como
requisito de arranque.

## 3. Modelo de usuario personalizado desde el día 1

`AUTH_USER_MODEL` se fijó a `apps.users.User` (subclase de `AbstractUser` con
email único) antes de la primera migración, porque cambiar el modelo de
usuario después de tener migraciones aplicadas es costoso en Django. El resto
del perfil (membresía, roles) se completa en la fase de Usuarios y
Membresías, no en el día de fundación.

## 4. Precisión financiera con `Decimal`

Todo cálculo monetario (tasas, spreads, montos) usa `Decimal`, nunca `float`.
El backend persiste la tasa efectiva usada en cada remesa al momento de
creación, para que transacciones históricas no cambien si el admin actualiza
las tasas después.

## 5. Proveedores externos como abstracción + mock

ETECSA y los proveedores de pago sin credenciales disponibles (Wise, Mercado
Pago, EnZona, Zelle) se implementan detrás de una interfaz (`RechargeProvider`,
`PaymentProvider`) con una implementación mock determinista para pruebas.
Stripe se integra en modo test si resulta práctico dentro del timebox.
