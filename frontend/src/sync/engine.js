// Motor de sincronización offline-first.
// Patrón: Outbox + Idempotent Replay.
//
// Cada operación local pasa por queueOp() → se guarda en IndexedDB.
// Un loop intenta drenar la outbox al servidor cada N segundos.
// El servidor responde por client_uuid: accepted | duplicate | conflict | error.
// Los accepted + duplicate se eliminan del local. Los error se reintentan con backoff.
import { db, getKV } from '../db.js'
import { api } from '../api.js'

const BATCH_SIZE = 50
const TICK_MS = 5000

function ulid() {
  // ULID simple: ms timestamp + random, en hex. Ordenable.
  const t = Date.now().toString(16).padStart(12, '0')
  const r = crypto.getRandomValues(new Uint8Array(10))
  return `${t}-${Array.from(r).map(b => b.toString(16).padStart(2, '0')).join('')}`
}

export function uuidv4() {
  return crypto.randomUUID()
}

export async function queueOp(op) {
  // op debe incluir kind + client_uuid ya generado por quien llama (para escribir
  // inmediatamente el estado local con el mismo ID).
  await db.outbox.add({
    kind: op.kind,
    client_uuid: op.client_uuid,
    payload: op,
    attempts: 0,
    next_try_at: Date.now(),
    created_at: Date.now(),
  })
}

function backoff(attempts) {
  // 2s, 4s, 8s, 30s, 120s, 300s…
  const ladder = [2000, 4000, 8000, 30000, 120000, 300000]
  return ladder[Math.min(attempts, ladder.length - 1)]
}

let running = false
export async function drainOnce() {
  if (running) return
  if (!navigator.onLine) return

  const deviceId = await getKV('device_id')
  const token = await getKV('token')
  if (!deviceId || !token) return

  running = true
  try {
    const now = Date.now()
    const pending = await db.outbox
      .where('next_try_at')
      .belowOrEqual(now)
      .limit(BATCH_SIZE)
      .toArray()

    if (pending.length === 0) return

    const ops = pending.map(p => p.payload)
    let response
    try {
      response = await api.syncBatch(deviceId, ops)
    } catch (err) {
      // Falló toda la red: subimos el contador de intentos y aplicamos backoff.
      for (const row of pending) {
        await db.outbox.update(row.seq, {
          attempts: row.attempts + 1,
          next_try_at: Date.now() + backoff(row.attempts + 1),
        })
      }
      console.warn('[sync] batch failed', err.message)
      return
    }

    const byUuid = Object.fromEntries(response.results.map(r => [r.client_uuid, r]))
    for (const row of pending) {
      const r = byUuid[row.client_uuid]
      if (!r) continue
      if (r.status === 'accepted' || r.status === 'duplicate') {
        await db.outbox.delete(row.seq)
        // Marcamos el espejo local como sincronizado.
        if (row.kind === 'sale') {
          await db.sales_local.update(row.client_uuid, { synced: 1 })
        } else if (row.kind === 'access') {
          await db.access_local.update(row.client_uuid, { synced: 1 })
        }
      } else if (r.status === 'conflict') {
        // Conflicto del servidor: lo logueamos y salimos de la outbox.
        // La UI debe haber manejado el caso al registrar la operación.
        console.warn('[sync] conflict', row.client_uuid, r.reason)
        await db.outbox.delete(row.seq)
      } else {
        await db.outbox.update(row.seq, {
          attempts: row.attempts + 1,
          next_try_at: Date.now() + backoff(row.attempts + 1),
        })
      }
    }
  } finally {
    running = false
  }
}

export function startSyncLoop() {
  // Drena al arrancar y cada TICK_MS. También cuando vuelve el internet.
  setInterval(drainOnce, TICK_MS)
  window.addEventListener('online', drainOnce)
  drainOnce()
}

export async function outboxCount() {
  return db.outbox.count()
}
