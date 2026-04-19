<script setup>
import { computed, onMounted, ref } from 'vue'
import { db, getKV } from '../db.js'
import { queueOp, uuidv4, drainOnce } from '../sync/engine.js'

const products = ref([])
const cart = ref([])
const paying = ref(false)
const lastTotal = ref(null)

onMounted(async () => {
  products.value = await db.products.orderBy('name').toArray()
})

const total = computed(() =>
  cart.value.reduce((acc, x) => acc + Number(x.unit_price) * x.qty, 0),
)

function add(p) {
  const existing = cart.value.find(x => x.product_id === p.id)
  if (existing) {
    existing.qty++
  } else {
    cart.value.push({
      product_id: p.id,
      name: p.name,
      unit_price: p.sale_price,
      qty: 1,
    })
  }
  // Actualización optimista del stock local para visibilidad.
  p.qty_on_hand = (p.qty_on_hand || 0) - 1
}

function removeLine(i) {
  cart.value.splice(i, 1)
}

async function charge(method) {
  if (!cart.value.length) return
  paying.value = true
  const clientUuid = uuidv4()
  const deviceId = await getKV('device_id')
  const ev = await db.event.toCollection().first()

  const payload = {
    kind: 'sale',
    client_uuid: clientUuid,
    event_id: ev?.id,
    device_id: deviceId,
    total: total.value.toFixed(2),
    payment_method: method,
    created_at: new Date().toISOString(),
    items: cart.value.map(x => ({
      product_id: x.product_id,
      qty: x.qty,
      unit_price: String(x.unit_price),
      discount: '0',
    })),
  }

  // 1) Escribir local de inmediato (ESTO es lo que nos salva si no hay internet).
  await db.sales_local.put({
    client_uuid: clientUuid,
    created_at: payload.created_at,
    event_id: payload.event_id,
    total: payload.total,
    items: payload.items,
    synced: 0,
  })

  // 2) Encolar para el servidor.
  await queueOp(payload)

  // 3) Confirmar a la cajera en la UI (no esperamos red).
  lastTotal.value = payload.total
  cart.value = []
  paying.value = false

  // 4) Intento best-effort de drenar ahora (no bloqueante si falla).
  drainOnce()
}
</script>

<template>
  <div class="h-full flex flex-col md:flex-row">
    <!-- Grid de productos -->
    <div class="flex-1 p-2 grid grid-cols-2 md:grid-cols-4 gap-2 overflow-auto">
      <button
        v-for="p in products"
        :key="p.id"
        class="tile flex flex-col items-start justify-between p-4 min-h-[120px]"
        :class="p.qty_on_hand <= 0 ? 'opacity-40' : ''"
        @click="add(p)"
      >
        <div class="font-display text-lg leading-tight">{{ p.name }}</div>
        <div class="flex justify-between w-full items-end">
          <span class="text-dim font-mono text-xs">stock {{ p.qty_on_hand }}</span>
          <span class="font-display text-2xl text-hot">${{ p.sale_price }}</span>
        </div>
      </button>
    </div>

    <!-- Ticket lateral -->
    <div class="w-full md:w-[360px] border-t-2 md:border-t-0 md:border-l-2 border-line bg-black flex flex-col">
      <div class="p-3 border-b-2 border-line font-mono text-sm text-dim">TICKET</div>
      <div class="flex-1 overflow-auto">
        <div
          v-for="(l, i) in cart"
          :key="i"
          class="flex items-center justify-between px-3 py-2 border-b border-line"
          @click="removeLine(i)"
        >
          <div>
            <div class="font-display">{{ l.name }}</div>
            <div class="text-dim font-mono text-xs">x{{ l.qty }} · ${{ l.unit_price }}</div>
          </div>
          <div class="font-display text-lg">${{ (l.qty * l.unit_price).toFixed(0) }}</div>
        </div>
      </div>

      <div class="p-3 border-t-2 border-line">
        <div class="flex justify-between items-center mb-3">
          <span class="font-mono text-dim">TOTAL</span>
          <span class="font-display text-4xl text-hot">${{ total.toFixed(0) }}</span>
        </div>
        <div class="grid grid-cols-2 gap-2">
          <button class="btn btn-hot" :disabled="paying || !cart.length" @click="charge('cash')">
            EFECTIVO
          </button>
          <button class="btn btn-ok" :disabled="paying || !cart.length" @click="charge('card')">
            TARJETA
          </button>
        </div>
        <div v-if="lastTotal" class="mt-3 bg-ok text-black font-display text-center p-2">
          COBRADO ${{ lastTotal }}
        </div>
      </div>
    </div>
  </div>
</template>
