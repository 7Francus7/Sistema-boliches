// IndexedDB local vía Dexie. Es nuestra "verdad offline".
import Dexie from 'dexie'

export const db = new Dexie('boliche_local')

db.version(1).stores({
  // Espejo de catálogo pre-cargado (solo lectura local mientras dura el evento)
  products: 'id, sku, name, category',
  tickets: 'id, qr_code, status, ticket_type_id',
  event: 'id',

  // Tablas transaccionales locales (se escriben offline)
  sales_local: 'client_uuid, created_at, event_id, synced',
  access_local: 'client_uuid, scanned_at, ticket_id, synced',

  // Outbox: operaciones pendientes de subir al servidor
  outbox: '++seq, kind, client_uuid, attempts, next_try_at',

  // Config del dispositivo (token, device_id, etc.)
  kv: 'key',
})

export async function setKV(key, value) {
  await db.kv.put({ key, value })
}
export async function getKV(key, fallback = null) {
  const row = await db.kv.get(key)
  return row ? row.value : fallback
}
