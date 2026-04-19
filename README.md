# Sistema Boliches · SaaS MVP

SaaS integral para gestión de boliches y discotecas.
**Filosofía offline-first**: si se cae internet, la barra sigue cobrando y la puerta sigue escaneando.

## Arquitectura

```
┌────────────────────────┐        ┌─────────────────────────┐
│  PWA (Vue 3 + Dexie)   │        │  FastAPI + PostgreSQL   │
│                        │        │                         │
│  IndexedDB ← verdad    │        │  /auth    (JWT)         │
│  Outbox   ← pendientes │  HTTPS │  /bootstrap  (catálogo) │
│  SW      ← sync bg     │ ──────▶│  /sync/batch (idempot.) │
│  POS / Puerta / Admin  │        │  /analytics  (admin)    │
└────────────────────────┘        └─────────────────────────┘
```

- **Idempotencia** por `client_uuid` en toda operación escritora.
- **Reconciliación** "first-write-wins" por `scanned_at` en accesos (QR).
- **Stock** con log inmutable (`stock_movements`) + tabla de estado (`stock_levels`).
- **QR** firmados con JWT → validables offline.

## Stack

**Backend:** FastAPI, SQLAlchemy 2, Postgres 16, PyJWT, Passlib.
**Frontend:** Vite + Vue 3 + Pinia, Dexie (IndexedDB), Workbox PWA, @zxing/browser (QR), Tailwind con tema utilitario.

## Arranque local

Requisitos: Docker + Node 20+.

```bash
# 1) Backend + DB
docker compose up --build

# 2) Frontend (en otra terminal)
cd frontend
npm install
npm run dev
```

- API: http://localhost:8000 (docs en `/docs`)
- App: http://localhost:5173

### Usuarios demo (seed automático)

| Rol     | Usuario                | Clave      |
|---------|------------------------|------------|
| Admin   | admin@demo.local       | admin123   |
| Cajero  | cajero@demo.local      | cajero123  |
| Puerta  | puerta@demo.local      | puerta123  |

## Probar el comportamiento offline

1. Loguearte como cajero y abrir `/pos`.
2. DevTools → Network → **Offline**.
3. Cargar productos al ticket y cobrar. La venta se confirma al instante.
4. Mirar el badge **COLA** en la barra superior: cuenta ops pendientes.
5. Volver a Online. La cola se drena sola (o tocar **SYNC**).
6. Refrescar Admin → ver la venta sincronizada en el dashboard.

## Estructura del repo

```
backend/
  app/
    main.py          # FastAPI app + lifespan + CORS
    config.py        # settings con pydantic-settings
    db.py            # SQLAlchemy engine + session
    models.py        # Schema completo (venues, sales, stock, tickets…)
    schemas.py       # Pydantic I/O
    security.py      # JWT, bcrypt, QR signing
    deps.py          # get_current_user, roles
    seed.py          # Seed idempotente (demo venue)
    routers/
      auth.py
      bootstrap.py
      sync.py        # ← núcleo del offline-first
      analytics.py

frontend/
  src/
    db.js            # Dexie schema local
    api.js           # Cliente HTTP
    router.js
    main.js
    App.vue
    sync/engine.js   # Outbox + drainOnce + backoff
    stores/session.js
    views/
      Login.vue
      Home.vue
      POS.vue        # ← 2 toques para cobrar
      Door.vue       # ← scan QR ultrarrápido
      Admin.vue
```

## Tests

```bash
cd backend
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest
```

14 tests cubren auth, bootstrap, idempotencia por `client_uuid`,
first-write-wins en accesos, decremento de stock, CRUD de productos y
el E2E completo de "noche offline → sync → dashboard".

## Impresión y barcode en el POS

- **ESC/POS**: la impresión del ticket busca Web Serial → Web Bluetooth →
  fallback HTML (abre una ventana imprimible). El toggle "IMPRIMIR" en
  la barra lateral desactiva la impresión si la ticketera está rota.
- **Lector de código de barras**: cualquier scanner USB en modo HID-keyboard
  se detecta automáticamente (latido rápido entre teclas + Enter final).
  Busca por `sku` en el catálogo local y agrega al ticket.

## Próximos pasos sugeridos

- [ ] Alertas UI para `conflict` de `/sync/batch`.
- [ ] Módulo de ventas online (ticketing + pago) → fee transaccional.
- [ ] Reportes de mermas (cuando stock proyectado diverge del real).
- [ ] Roles más granulares + auditoría.
- [ ] Playwright para E2E del PWA real con red simulada.

## Roadmap comercial

Ver `docs/PITCH.md` y `docs/BUSINESS_MODEL.md` (por crear).
Modelo recomendado: **fin de semana gratis + suscripción USD 120-180/mes + 3% sobre ticketing online**.
