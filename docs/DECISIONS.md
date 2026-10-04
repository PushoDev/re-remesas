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

## 6. Login por email y roles con `is_staff`

`User.USERNAME_FIELD = 'email'`: el correo es el identificador de acceso, se
guarda normalizado en minúsculas y la unicidad se valida sin distinguir
mayúsculas (`A@x.com` y `a@x.com` son la misma cuenta). `username` se conserva
porque `AbstractUser` lo exige y se rellena con el correo. La spec solo define
dos roles —cliente y administrador (`IsAdminUser`)—, así que el rol admin es
`is_staff` y no se añaden grupos ni permisos propios.

## 7. Membresía en un `Profile`, con el estado calculado

`Profile` (uno a uno con `User`, creado por una señal `post_save` para todo
usuario) guarda `is_membership_active` y `membership_expires_at`. El estado
que consume el resto del sistema es `membership_status` (`FREE`/`VIP`), una
propiedad calculada: solo es VIP si la membresía está activa **y** no ha
vencido. Una membresía vencida deja de contar sin depender de ninguna tarea
programada. El frontend nunca decide quién es VIP: lo toma de la API.

## 8. Sesión: access en memoria, refresh en cookie `httpOnly`

- El **access token** (30 min) vive solo en memoria de la aplicación React: no
  se guarda en `localStorage` ni `sessionStorage`.
- El **refresh token** (7 días) viaja únicamente en una cookie `HttpOnly`,
  `SameSite=Lax`, con `Path=/api/auth/` y `Secure` configurable
  (`AUTH_COOKIE_SECURE`). Ningún cuerpo de respuesta lo incluye, así que un XSS
  no puede leerlo.
- Rotación con lista negra (`ROTATE_REFRESH_TOKENS` + `BLACKLIST_AFTER_ROTATION`):
  un refresh usado o cerrado no se puede reutilizar. `POST /api/auth/logout/`
  lo invalida en el servidor y borra la cookie.
- Al cargar la app, React recupera la sesión pidiendo un access nuevo con la
  cookie; si hay varias peticiones con 401 a la vez, comparten **una sola**
  renovación (el refresh rota, una segunda llamada en paralelo sería rechazada).
- Registro y login entregan el mismo resultado: access en el cuerpo y refresh
  en la cookie; el registro deja al usuario con la sesión iniciada.

**Limitación conocida:** con la rotación, dos pestañas que renuevan a la vez
con la misma cookie pueden hacer que una pierda la sesión. Se acepta para el
alcance de la prueba.

## 9. Mismo origen entre frontend y API (proxy)

La cookie de sesión exige que frontend y API sean del mismo sitio. En desarrollo
el navegador solo habla con el origen del frontend y Vite reenvía `/api` a
Django (`server.proxy`); `VITE_API_BASE_URL=/api`. Así la cookie es de primera
parte y no hace falta CORS con credenciales desde el navegador. En un despliegue
real el equivalente es publicar frontend y `/api` bajo el mismo dominio con un
proxy inverso.

## 10. Contraseñas: el backend manda, el frontend solo orienta

Reglas de HU-AUTH-01: mínimo 8 caracteres, con letras y números. El backend las
aplica con los validadores de Django (largo mínimo, no común, no solo numérica,
no parecida al correo) más un validador propio de letra y número. El formulario
de registro repite las reglas solo para dar retroalimentación inmediata
(requisitos en vivo); si el backend rechaza algo, su mensaje se muestra bajo el
campo correspondiente.

## 11. Pruebas y datos de demostración

- Backend: `pytest` + `pytest-django` sobre la misma base Postgres de
  desarrollo (base de pruebas aparte). Cubre modelo, reglas de contraseña,
  registro, login, refresh, logout, `/users/me/`, cookie y admin.
- Frontend: Vitest para la lógica sin interfaz (renovación de sesión en el
  cliente HTTP, servicios, esquemas de validación, helpers de membresía).
- `manage.py seed_demo_users` crea un usuario por rol/estado (admin, cliente,
  VIP y VIP vencido) con una contraseña de demostración. Es solo para
  desarrollo; los atajos de "cuentas de prueba" de la pantalla de login solo se
  renderizan en modo desarrollo (`import.meta.env.DEV`) y no existen en el build
  de producción.

## 12. Tasas de cambio: una tabla administrada, no una API externa

La spec habla de consultar "la API de tasas (ExchangeRate)". No hay proveedor ni
credenciales, así que `ExchangeRate` es una entidad propia que el administrador
mantiene (base, margen estándar y margen VIP por moneda). Si en el futuro se
integra un proveedor externo, solo tendría que alimentar esa misma tabla: el
resto del sistema consume el servicio `exchange_rates.services`, no la fuente.
Los datos de demostración (`seed_demo_rates`) **no son tasas reales de mercado**;
USD 700 es el ejemplo de la spec.

## 13. Cálculo de la tasa efectiva y redondeo

`tasa_efectiva = tasa_base × (100 − margen) / 100`; el margen VIP reemplaza al
estándar para un miembro **vigente**. Todo en `Decimal`:

- tasa efectiva a 4 decimales, `ROUND_HALF_UP`;
- monto en CUP a 2 decimales, `ROUND_DOWN`: al cliente nunca se le promete más
  que (tasa mostrada × monto).

Hay un único punto de cálculo (`convert()`); remesas y cualquier otra cotización
pasan por él. Las reglas de negocio viven también en la base de datos
(`CheckConstraint`): tasa > 0, márgenes en [0, 100), margen VIP ≤ estándar, y
una sola tasa activa por moneda.

## 14. Historial y desactivación en lugar de borrado

Cada alta o cambio de una tasa escribe una fila inmutable en
`ExchangeRateHistory` (valores, autor y fecha) dentro de la misma transacción.
`DELETE` en la API **desactiva** la tasa en vez de borrarla, para no perder la
auditoría; una tasa desactivada puede reemplazarse por una nueva activa. Las
remesas guardan una instantánea de la tasa usada, de modo que cambiar o
desactivar una tasa no altera transacciones pasadas.

## 15. Endpoint público de tasas: lo que ve quien pregunta

`GET /api/exchange-rates/` devuelve la tasa **tal como la recibiría quien
consulta** (estándar, o preferencial si es miembro vigente) y `Cache-Control:
no-store` para que un cambio del administrador se vea en la siguiente petición.
Nunca expone el margen VIP ni la tasa VIP a quien no es miembro. En el frontend
la vista previa del formulario de administración usa aritmética entera
(`BigInt`) con el mismo redondeo; es solo orientativa y nunca se usa para una
transacción: el servidor es la autoridad.

## 16. Capa de pagos con proveedores intercambiables (y qué es real)

`apps/payments` define `Payment` (propósito, monto instantánea, método, estado)
y la interfaz `PaymentProvider`. Un único archivo (`providers/registry.py`)
decide qué proveedor atiende cada método de pago; el negocio nunca ramifica por
proveedor. **No hay ninguna integración viva con una pasarela**, y no se finge:

| Método | Lo atiende | Qué es |
|---|---|---|
| Stripe, PayPal, Mercado Pago, EnZona | `MockPaymentProvider` | Pasarela **simulada**: no se cobra nada; el cliente pasa por una página de pago de la propia app |
| Wise, Zelle, Efectivo | `ManualPaymentProvider` | Se pagan fuera de la app; un administrador verifica el comprobante y confirma |

Sustituir el simulado por Stripe (modo test) o por otra pasarela es escribir un
proveedor y cambiar una línea del registro; no toca membresías, remesas ni
recargas. Stripe real no se implementó por quedar fuera del alcance disponible.

## 17. La confianza de un pago viene de la firma, no del navegador

Solo un webhook verificado (o un administrador, en los métodos manuales) activa
algo. Volver a la página tras pagar no activa nada; la pantalla de resultado
consulta el estado real del pago a la API. El webhook es público (la pasarela no
tiene sesión), así que se autentica únicamente por la firma HMAC-SHA256 del
cuerpo, que se verifica antes de buscar o modificar nada. El checkout simulado
construye el mismo evento firmado y pasa por el mismo manejador, de modo que el
camino real queda ejercitado; solo existe con `PAYMENT_MOCK_ENABLED` (por
defecto, solo en desarrollo) y solo para el dueño del pago. El precio se lee
siempre del plan en el servidor.

## 18. Un pago se liquida una sola vez

`settle_payment` bloquea la fila del pago (`select_for_update`) y solo actúa si
sigue `PENDING`: la primera confirmación lo pasa a `SUCCEEDED`/`FAILED` y ejecuta
el manejador de su propósito; cualquier confirmación posterior se ignora. Un
webhook reenviado no puede aplicar el efecto dos veces, un fallo tardío no
deshace un pago cobrado y un éxito tardío no revive uno fallido. Si el manejador
falla, la transacción se revierte y el pago sigue pendiente para reintentarse.
Cada app (membresías ahora; remesas y recargas después) registra su manejador.

## 19. Reglas de activación y extensión de la membresía

- Sigue vigente: el periodo nuevo se suma **después** de la expiración actual.
- Gratuita o vencida: empieza hoy (no se cuenta desde una fecha pasada).
- VIP sin fecha de fin (concedido por un administrador): nunca se acorta.
- Varias compras se acumulan.
- La suscripción guarda una instantánea de la duración y del descuento de
  recargas del plan; editar el plan después no altera compras anteriores.
- La compra de un plan (`subscribe`) crea el pago y la suscripción
  **pendientes**; la membresía no cambia hasta que el pago se confirma.

El beneficio de las remesas no vive en el plan sino en el margen VIP de la tasa
de cambio (decisión 13): hay una sola fuente de verdad para el margen.

## 20. Pagos manuales resueltos desde el admin de Django

Mientras no existe el panel de remesas, un administrador confirma o rechaza los
pagos manuales con las acciones del admin de Django sobre `Payment`. Esas
acciones solo actúan sobre pagos manuales que siguen pendientes y pasan por
`settle_payment`, con la misma garantía de una sola liquidación. Los pagos y las
suscripciones son de solo lectura en el admin: cambian únicamente a través del
flujo de pago.
