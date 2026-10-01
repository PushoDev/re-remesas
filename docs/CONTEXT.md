# CONTEXT.md — Ideas y estructuras especulativas (NO entregable)

> ⚠️ Este archivo vive solo en la rama `feature/desarrollo`. **No se mergea a
> `main`.** Es un scratchpad de ideas propias para pensar en voz alta mientras
> se desarrolla, no compromisos de alcance ni parte de la entrega final.
>
> La fuente de verdad del alcance sigue siendo
> `Especificacion_Re_y_Re_Remesas_Recargas.pdf` y
> `CONTEXT_Re_Re_Technical_Assessment.md` (fuera de este repo, en
> `Pruebas.Tecnicas/djasoft/`). Nada de lo que sigue debe interpretarse como
> una ampliación del alcance exigido — son opciones a evaluar *si sobra
> tiempo*, nunca a costa de las 6 historias de usuario obligatorias.

## Cómo usar este documento

- Marcar cada idea como `[ ] evaluando`, `[x] adoptada` o `[-] descartada`
  a medida que se decide.
- Antes de mergear a `main`: borrar este archivo o mover a
  `docs/DECISIONS.md` solo lo que realmente se implementó.

---

## 1. Estructuras de datos posibles (más allá del mínimo)

### `users` / `memberships`
- [ ] `Contact` (contactos recientes del remitente) — la spec lo menciona
  explícitamente en HU-TOP-01 ("seleccionar de sus contactos recientes un
  número cubano"). Mínimo viable: lista de números +53 guardados por
  usuario, reutilizable también en `remittances` (destinatarios frecuentes).
- [ ] Roles explícitos (`Role`/`Group` de Django) en vez de un simple
  `is_staff`/`is_admin` — solo si el panel admin necesita más de un nivel
  (ej. "gestor de remesas" vs "gestor de tasas"). La spec solo pide un rol
  admin genérico (`IsAdminUser`), así que por defecto **no** hace falta.

### `remittances`
- [ ] `RemittanceStatusLog` (tabla de auditoría de cambios de estado: quién,
  cuándo, de qué estado a cuál) — no es un requisito explícito, pero ayuda
  a demostrar buen juicio de ingeniería (trazabilidad) sin inventar
  funcionalidad de negocio nueva.
- [ ] Tracking ID legible: formato propuesto `RR-YYYYMMDD-XXXXX` (prefijo +
  fecha + sufijo aleatorio corto) — evaluar contra "humanamente legible
  para soporte" (requisito explícito de la spec, sección 10 del
  CONTEXT.md original).

### `exchange_rates`
- [ ] Historial explícito vía tabla append-only (`ExchangeRateSnapshot`) en
  vez de solo versionar con `updated_at` — ya es semi-requisito ("marca de
  tiempo", "historial" en la spec), decidir si una tabla separada aporta
  claridad o es sobre-ingeniería para el timebox.

### `recharges`
- [ ] `Promotion` como modelo propio (código, descripción, vigencia) en vez
  de un campo suelto — la spec pide "detectar promoción ETECSA activa
  inyectada desde el backend", así que algún modelo hace falta; decidir
  nivel de detalle (¿aplica a un paquete específico o es global?).

---

## 2. Funcionalidades opcionales (si sobra tiempo)

- [ ] **Notificación de cambio de estado** vía polling corto en el frontend
  (la spec lo pide explícitamente: "El cambio de estado debe disparar una
  notificación... en la Web App del cliente", HU-REM-02). Opción mínima:
  el frontend re-consulta el estado cada N segundos en la página de
  tracking. Opción más elaborada (evaluar si hay tiempo): WebSocket /
  Server-Sent Events — probablemente over-engineering para el timebox.
- [ ] **Documentación OpenAPI autogenerada** (`drf-spectacular`) — no lo
  pide la spec, pero resuelve "documentar los endpoints de la API"
  (sección 21, Definition of Done) sin mantenerla a mano.
- [ ] **Rate limiting** en `/api/auth/login/` (django-ratelimit o
  throttling nativo de DRF) — mencionado solo indirectamente ("seguridad
  mínima"); evaluar si vale la pena dentro del timebox o es alcance extra.
- [ ] **Datos semilla / demo** (`manage.py seed_demo_data`) — sí es
  requisito explícito (sección 20, Día 7: "Seed/demo data"), decidir aquí
  el detalle: cuántos usuarios, remesas en cada estado, etc.

## 3. Alternativas estructurales (backend)

- [ ] Capa de servicios explícita (`apps/<app>/services.py`) separando
  lógica de negocio de las vistas/serializers — ayuda a mantener los
  cálculos financieros testeables de forma aislada. Evaluar si se adopta
  desde `remittances`/`exchange_rates` (donde más importa) o en todas las
  apps por consistencia.
- [ ] Proveedores seleccionables por variable de entorno
  (`PAYMENT_PROVIDER=mock|stripe`, `RECHARGE_PROVIDER=mock`) en vez de
  lógica condicional en código — hace explícito en `.env.example` qué está
  mockeado sin tocar código para cambiarlo.

## 4. Alternativas estructurales (frontend)

- [ ] Componente compartido `Money` / `CurrencyAmount` para formatear
  todos los montos de forma consistente (símbolo, separadores, decimales)
  en vez de formatear ad-hoc en cada página — baja complejidad, alto
  impacto en "comunicar información financiera con claridad" (sección 16
  del CONTEXT.md original).
- [ ] Tipos TypeScript generados desde el schema OpenAPI del backend (si
  se adopta `drf-spectacular` arriba) en vez de tipos escritos a mano —
  mantiene el contrato de API sincronizado sin esfuerzo manual duplicado.
- [ ] React Query (o SWR) para el cache/estado de las llamadas a la API en
  vez de `useEffect` + `useState` sueltos — mejora estados de carga/error
  de forma consistente, que la spec sí exige explícitamente (sección 16).

---

## Notas

- Nada de esta lista es obligatorio. Las 6 historias de usuario y sus
  criterios de aceptación (ver especificación original) son lo único que
  define "terminado".
- Si una idea de acá se adopta, documentarla en `docs/DECISIONS.md` (ese sí
  llega a `main`) y borrarla de esta lista para no duplicar.
