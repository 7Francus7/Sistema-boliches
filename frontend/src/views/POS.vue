<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { db, getKV } from '../db.js'
import { queueOp, uuidv4, drainOnce } from '../sync/engine.js'
import { printTicket } from '../pos/escpos.js'
import { installBarcodeListener } from '../pos/barcode.js'

const products = ref([])
const cart = ref([])
const paying = ref(false)
const lastTotal = ref(null)
const feedback = ref('')
const autoPrint = ref(true)
let removeBarcodeListener = null

onMounted(async () => {
  products.value = await db.products.orderBy('name').toArray()
  removeBarcodeListener = installBarcodeListener((code) => {
    const p = products.value.find((x) => x.sku === code)
    if (p) {
      add(p)
      flash(`+ ${p.name}`)
    } else {
      flash(`SKU ${code} NO ENCONTRADO`, true)
    }
  })
})

onBeforeUnmount(() => {
  if (removeBarcodeListener) removeBarcodeListener()
})

const total = computed(() =>
  cart.value.reduce((acc, x) => acc + Number(x.unit_price) * x.qty, 0),
)

function flash(text, error = false) {
  feedback.value = (error ? '× ' : '') + text
  setTimeout(() => (feedback.value = ''), 900)
}

function add(p) {
  const existing = cart.value.find((x) => x.product_id === p.id)
  if (existing) existing.qty++
  else
    cart.value.push({
      product_id: p.id,
      name: p.name,
      unit_price: p.sale_price,
      qty: 1,
    })
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
    items: cart.value.map((x) => ({
      product_id: x.product_id,
      qty: x.qty,
      unit_price: String(x.unit_price),
      discount: '0',
    })),
  }

  await db.sales_local.put({
    client_uuid: clientUuid,
    created_at: payload.created_at,
    event_id: payload.event_id,
    total: payload.total,
    items: payload.items,
    synced: 0,
  })

  await queueOp(payload)

  // Snapshot para la impresora ANTES de vaciar el carrito.
  const ticketPayload = {
    venue: 'BOLICHE',
    event: ev?.name || '',
    sale: payload,
    items: cart.value.map((x) => ({ ...x })),
  }

  lastTotal.value = payload.total
  cart.value = []
  paying.value = false

  drainOnce()

  if (autoPrint.value) {
    try {
      await printTicket(ticketPayload)
    } catch (e) {
      console.warn('[pos] print error', e.message)
    }
  }
}
</script>

<template>
  <div class="h-full flex flex-col md:flex-row">
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
          <span class="text-dim font-mono text-xs">{{ p.sku }} · {{ p.qty_on_hand }}</span>
          <span class="font-display text-2xl text-hot">${{ p.sale_price }}</span>
        </div>
      </button>
    </div>

    <div class="w-full md:w-[360px] border-t-2 md:border-t-0 md:border-l-2 border-line bg-black flex flex-col">
      <div class="p-3 border-b-2 border-line font-mono text-sm flex justify-between items-center">
        <span class="text-dim">TICKET</span>
        <label class="text-xs flex items-center gap-2 cursor-pointer">
          <input v-model="autoPrint" type="checkbox" class="w-4 h-4" /> IMPRIMIR
        </label>
      </div>

      <div class="flex-1 overflow-auto">
        <div
          v-for="(l, i) in cart"
          :key="i"
          class="flex items-center justify-between px-3 py-2 border-b border-line cursor-pointer"
          @click="removeLine(i)"
        >
          <div>
            <div class="font-display">{{ l.name }}</div>
            <div class="text-dim font-mono text-xs">x{{ l.qty }} · ${{ l.unit_price }}</div>
          </div>
          <div class="font-display text-lg">${{ (l.qty * l.unit_price).toFixed(0) }}</div>
        </div>
      </div>

      <div v-if="feedback" class="bg-hot text-black font-display text-center p-2">
        {{ feedback }}
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
