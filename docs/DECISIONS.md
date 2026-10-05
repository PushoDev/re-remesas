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

## 21. La remesa guarda una instantánea y el servidor manda

Al crear una remesa se guarda, junto a ella, todo lo que importa del dinero:
tasa base, margen aplicado, tasa efectiva, monto en CUP y si fue tarifa VIP.
Cambiar o desactivar una tasa después **no altera** remesas existentes. El
cliente solo decide monto, moneda, destinatario, método de entrega y medio de
pago: cualquier tasa, monto en CUP, estado, ID, remitente o marca VIP que envíe
se **ignora**, y todo se recalcula en el servidor con `convert()` (decisión 13).
El navegador nunca calcula dinero: la calculadora muestra únicamente lo que
devuelve `POST /api/remittances/quote/`, y la vista previa de administración
(decisión 15) es solo orientativa.

## 22. ID de seguimiento legible y no adivinable

Formato `RR-YYYYMMDD-XXXXX`. El sufijo son 5 caracteres de un alfabeto de 32
(sin `0/O/1/I`, para dictarlo sin confusiones) generados con `secrets`: unos 33
millones de combinaciones por día, de modo que el ID de otra persona no se
deduce del propio. Es único por restricción de base de datos; si dos remesas
chocaran, la creación reintenta con otro ID dentro de un *savepoint* y, si no
logra uno libre, falla limpiamente sin dejar datos a medias. El cliente nunca
ve el `id` interno.

## 23. Creación atómica y reacción mínima al pago

Crear la remesa, su pago pendiente y el vínculo entre ambos ocurre en una sola
transacción: si el proveedor de pago falla, no queda nada. Mientras no existe la
máquina de estados completa, el pago confirmado marca la remesa como `PAID` y un
pago fallido la `CANCELLED` (el cliente crea una nueva). Esa reacción vive en un
manejador registrado en la capa de pagos (decisión 18), por lo que una
confirmación repetida no la aplica dos veces.

## 24. Aislamiento: lo ajeno no existe

`GET /api/remittances/` y el detalle solo devuelven remesas del propio usuario.
Pedir la de otra persona o una inexistente da **el mismo 404** con el mismo
cuerpo, así que no se puede averiguar qué IDs existen; ni un administrador ve
las ajenas por la API de cliente. El listado va paginado, con filtros por estado
y búsqueda por parte del ID, y el número de consultas no crece con el historial.

## 25. Supuestos y límites de la remesa (no vienen en la especificación)

- Monto por remesa entre **1,00 y 10.000,00** de la moneda enviada
  (`REMITTANCE_MIN_AMOUNT` / `REMITTANCE_MAX_AMOUNT`), con máximo 2 decimales.
  Se rechaza la notación exponencial (`1e3`) y la coma en la API.
- Teléfono del destinatario: **móvil cubano** (`+53` y 8 dígitos que empiezan por
  5), normalizado a `+53XXXXXXXX`; la regla vive en un módulo común que reutilizan
  las recargas.
- Transferencia local: cuenta o tarjeta del destinatario de **12 a 20 dígitos**.
  El dato que el método de entrega no usa no se guarda.
- Medios de pago: los 6 de la historia más Zelle (que aparece en la verificación
  de administración).

**Limitaciones conocidas:** no hay clave de idempotencia para un doble envío del
formulario (el botón se deshabilita mientras se envía); la cotización pública no
tiene límite de peticiones; un pago fallido cancela la solicitud en lugar de
permitir reintentarla.

## 26. Redirecciones solo a rutas internas

Tras pagar en la pasarela simulada, la aplicación vuelve a la página indicada en
`?next=`. Como ese valor viaja en la URL no es de fiar: solo se acepta una ruta
interna (empieza por una sola `/`, sin `\` ni caracteres de control); cualquier
otra cosa (`https://…`, `//…`, `javascript:`) se descarta y se usa un destino
seguro por defecto, evitando una redirección abierta.

## 27. Máquina de estados de la remesa y bitácora inmutable

Un único lugar (`change_status`) decide qué movimientos son legales, con la
tabla de la especificación: `PENDING_PAYMENT → PAID | CANCELLED` y
`PAID → COMPLETED | CANCELLED`; `COMPLETED` y `CANCELLED` son finales. Cualquier
otro cambio se rechaza con un mensaje claro. Cada cambio escribe una entrada en
`RemittanceStatusLog` (estado anterior y nuevo, **fuente** —cliente, pago o
administrador—, quién, nota y fecha), que nunca se edita ni se borra; la creación
es la primera entrada. Una cancelación hecha por un administrador **exige un
motivo**. La fila se bloquea mientras se cambia, de modo que dos personas actuando
a la vez no pueden salir ambas bien.

## 28. Quién confirma qué: la pasarela se confirma sola

- Un pago por **pasarela** (simulada) lo confirma el propio webhook (decisión 17);
  un administrador **no puede marcarlo como pagado a mano**, para que nadie "cobre"
  algo que no se pagó.
- Un pago **manual** (Zelle, Wise, efectivo) lo confirma un administrador tras
  revisar el comprobante; queda registrado qué administrador lo hizo
  (`Payment.confirmed_by`).
- Cancelar una remesa cierra su pago pendiente, así un aviso tardío de la pasarela
  no la revive. Si el dinero llega para una remesa ya cancelada, el estado no se
  mueve pero se deja una **nota visible** de que requiere revisión y reembolso
  manual.
- El servidor indica en cada detalle qué acciones son posibles ahora
  (`allowed_actions`) y la pantalla pinta solo esos botones.

## 29. Orden de bloqueo: primero el pago, luego la remesa

Un webhook liquida el pago (bloqueándolo) y su manejador toca después la remesa;
las acciones del administrador siguen **el mismo orden**. Con un orden único es
imposible que un administrador y una pasarela actuando a la vez se esperen
mutuamente (interbloqueo).

## 30. Comprobantes de pago: archivos privados validados por su contenido

El cliente puede enviar una referencia y/o un archivo (solo en pagos manuales y
mientras la remesa espera el pago).

- Solo **JPG, PNG o PDF** de hasta **5 MB**, y se comprueba el **contenido real**
  (la firma del archivo), no el nombre: un ejecutable renombrado `.png` se rechaza.
  El cliente repite estas comprobaciones antes de subir, solo por comodidad.
- Se guarda con un **nombre aleatorio** en una carpeta privada. **No existe URL
  pública**: el administrador lo descarga con una petición autenticada, con
  `nosniff` y `private, no-store`, y la pantalla lo muestra desde memoria.
- Reenviar reemplaza el archivo y borra el anterior; cada envío queda en la bitácora.
- Al cliente se le muestra una **línea de tiempo segura**: estados y fechas, sin
  notas internas ni el correo de quien actuó.

## 31. Aviso al cliente por actualización periódica, no por WebSockets

La especificación pide notificar el cambio de estado "o actualizar la visualización".
La página de seguimiento se refresca sola cada 10 s mientras la remesa pueda cambiar
(la lista cada 15 s y el panel de administración cada 20 s) y muestra un aviso al
detectar un cambio. Se descartan WebSockets o *server-sent events* por
sobre-ingeniería para el alcance de la prueba. **Limitación:** hay hasta unos
segundos de retraso y no se envían correos ni SMS.

## 32. API y panel de administración

La administración usa el **ID de seguimiento** (no el `id` interno) y solo la
pueden usar usuarios `is_staff`. La bandeja admite filtro por los 4 estados,
búsqueda (ID, correo del remitente, nombre o teléfono del destinatario), orden y
paginación, con un número constante de consultas. El resumen del panel incluye, además
de los totales por estado, **«por revisar»**: pagos manuales aún pendientes en los
que el cliente ya envió referencia o archivo, que es lo que realmente espera a un
administrador.

**Limitaciones conocidas:** el reembolso de una remesa cancelada tras pagarse es
manual; solo se conserva el último comprobante enviado; los archivos no pasan por
un antivirus.

## 33. Recargas: solo móviles cubanos, con un único validador

Una recarga solo se acepta para un **móvil cubano**: `+53` seguido de 8 dígitos
que empiezan por 5. Los teléfonos fijos no se recargan y se rechazan con un
mensaje claro. Se admiten las formas habituales de escribirlo (`5123 4567`,
`+53 5123 4567`, `53-51234567`) y siempre se guarda normalizado como
`+53XXXXXXXX`. Es **el mismo validador** (`apps/common/phone.py`) que usan los
destinatarios de las remesas, para que no existan dos reglas distintas; el
frontend conserva una copia solo para dar respuesta inmediata, y quien decide es
el servidor. **Supuesto:** la regla del prefijo 5 es la de los móviles cubanos
actuales; no viene en la especificación.

## 34. Catálogo y promociones: las decide el servidor y solo informan

Cada paquete (saldo, datos, voz o combinado) tiene su precio en USD. La
**promoción vigente la decide el servidor**, no el navegador: una promoción está
vigente si está activa y la hora actual cae dentro de su ventana (el inicio
cuenta, el fin no). La API de paquetes la entrega como `active_promotion` y la
pantalla solo la dibuja; el catálogo no se guarda en caché porque las promociones
empiezan y terminan con el reloj.

- Si varias aplican a un mismo paquete, gana la hecha **para ese paquete** sobre
  la general y, entre iguales, la que **termina antes**. Es una regla propia, la
  especificación no la define.
- Una promoción **no cambia lo que se cobra**: es una bonificación para quien
  recibe la recarga. Se guarda una copia de la vigente en la orden (instantánea).

## 35. Precio de una recarga y descuento VIP

El precio lo calcula siempre el servidor, en `Decimal`: la cotización es
informativa y crear la orden la repite, así que ningún importe, estado ni
propietario enviado por el cliente llega a la base de datos. El cliente solo
decide teléfono, paquete y medio de pago.

- **Quién tiene descuento:** solo un VIP real (membresía activa y no vencida) con
  una **suscripción en curso**. Se aplica el porcentaje que quedó guardado al
  comprarla, no el actual del plan, de modo que editar un plan no altera lo ya
  vendido. Si hay varias en curso a la vez, aplica la mejor; una que empieza más
  adelante no cuenta todavía.
- **VIP concedido a mano sin suscripción:** paga el precio completo, porque no hay
  plan del que tomar el porcentaje.
- **Redondeo:** el descuento se redondea a céntimos, mitad hacia arriba. El total
  nunca supera el precio base ni baja de 0,01, y la base de datos lo exige con
  restricciones.
- La orden guarda precio base, porcentaje aplicado, total y moneda; un cambio
  posterior de precios no la altera.

## 36. Proveedor de recargas simulado

No hay contrato ni credenciales de ETECSA, y **no se finge una integración
viva**. Las recargas se piden a un `RechargeProvider` (una interfaz con una sola
función) que un único archivo (`providers/registry.py`) resuelve; sustituirlo por
uno real es escribir esa clase y cambiar una línea. Hoy solo existe el simulado:

| Qué | Cómo se resuelve | Qué es |
|---|---|---|
| Recarga a un móvil de ETECSA | `MockRechargeProvider` | **Simulado**: no se envía nada a nadie; responde según el último dígito del teléfono |

**Reglas del simulado (reproducibles a propósito):** el último dígito `0` →
**Fallida**; `1` → **Procesando** (queda sin completarse); cualquier otro →
**Exitosa**. Siempre devuelve una referencia propia (`RC-…`) y un mensaje en
español. Esto permite probar los tres caminos a voluntad.

Al cliente **no se le dice** que el proveedor es simulado: ve el mismo mensaje que
daría uno real. La divulgación es esta documentación y la tabla de integraciones
del README, no la interfaz.

## 37. Ciclo de una orden de recarga y una sola llamada al proveedor

Estados: `PENDING_PAYMENT → PROCESSING | SUCCESS | FAILED`. La orden nace con su
pago pendiente y **el proveedor no se llama al crearla**; solo se le pide la
recarga cuando el pago se confirma (por el webhook de la pasarela o por un
administrador en un pago manual).

- La orden se **bloquea** y solo se envía si sigue pendiente de pago: confirmar el
  mismo pago dos veces, o repetir el mismo webhook, pide la recarga **una sola
  vez**.
- Un pago que falla deja la orden en `FAILED` sin tocar al proveedor, y un aviso
  de éxito tardío no la revive.
- Se reutiliza la capa de pagos (decisión 16): la recarga solo registra qué hacer
  cuando su pago se resuelve. Se mantiene el orden de bloqueo de la decisión 29
  (primero el pago, luego la orden).

## 38. Si el proveedor falla: sin reintentos y con reembolso manual

Si el proveedor rechaza la recarga, o lanza un error o no responde, la orden
queda `FAILED` y **no se reintenta**: un reintento podría recargar dos veces el
mismo número. El detalle técnico del error nunca llega al cliente, que ve un
mensaje genérico.

El pago ya estaba cobrado, así que una orden `FAILED` con pago `SUCCEEDED` es un
**reembolso pendiente**. No hay reembolso automático: el listado de
administración la marca como *Reembolsar* y el cliente lee que se revisará su
reembolso. Un pago que nunca se cobró (falló en la pasarela) no se marca.

**Limitaciones conocidas:**
- Una orden en `PROCESSING` no se resuelve sola: no hay consulta de estado ni
  webhook del operador simulado, así que se queda así hasta que alguien actúe.
- No hay reintentos automáticos ni reembolsos reales.
- La llamada al proveedor ocurre dentro de la transacción que liquida el pago;
  con un operador real y lento convendría moverla a una tarea en segundo plano.

## 39. API y pantallas de recargas

- Cada orden se identifica en las URLs por una **referencia UUID**, no por su `id`
  numérico, para que no se pueda adivinar la de otro cliente. La orden de otro
  usuario, o una que no existe, responde **404**: su existencia no se revela
  (decisión 24).
- Los **contactos recientes** se derivan de las órdenes del propio usuario
  (números distintos, el más reciente primero, hasta 8); no hay una tabla de
  contactos aparte.
- **Solo pasarelas en línea en pantalla** (Stripe, PayPal, Mercado Pago y EnZona,
  todas simuladas, decisión 16), que es lo que pide la especificación ("pasarelas
  integradas"). Wise, Zelle y efectivo exigen que el cliente envíe un
  comprobante, y para recargas no existe esa subida. El servidor sí acepta los
  métodos manuales: un administrador los confirma desde el admin de Django
  (decisión 20), pero sin comprobante que revisar.
- El administrador dispone de un listado de todas las órdenes (filtro por estado,
  búsqueda por teléfono, correo o referencia, paginación) con el estado de pago,
  lo que respondió el operador y la marca de reembolso. Como el cliente, ve los
  cambios por actualización periódica (decisión 31).
