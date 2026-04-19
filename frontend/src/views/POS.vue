<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { db, getKV } from '../db.js'
import { queueOp, uuidv4, drainOnce } from '../sync/engine.js'
import { printTicket } from '../pos/escpos.js'
import { installBarcodeListener } from '../pos/barcode.js'
import { api } from '../api.js'

const products = ref([])
const cart = ref([])
const paying = ref(false)
const lastTotal = ref(null)
const feedback = ref('')
const autoPrint = ref(true)
const shift = ref(null)
const openingCash = ref('0')
const closingCash = ref('')
const closeNotes = ref('')
const showOpen = ref(false)
const showClose = ref(false)
const tabPrompt = ref(false)
const tabCode = ref('')
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
  await refreshShift()
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

async function refreshShift() {
  try {
    const deviceId = await getKV('device_id')
    if (!deviceId) return
    shift.value = await api.currentShift(deviceId)
  } catch (e) {
    console.warn('[pos] refreshShift', e.message)
  }
}

async function doOpenShift() {
  try {
    const deviceId = await getKV('device_id')
    const ev = await db.event.toCollection().first()
    const s = await api.openShift(deviceId, ev?.id, openingCash.value || '0')
    shift.value = s
    showOpen.value = false
    flash('TURNO ABIERTO')
  } catch (e) {
    flash(e.message, true)
  }
}

async function doCloseShift() {
  try {
    const body = await api.closeShift(shift.value.id, closingCash.value || '0', closeNotes.value)
    showClose.value = false
    flash(`ARQUEO: variance ${body.cash_variance}`)
    shift.value = null
  } catch (e) {
    flash(e.message, true)
  }
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
  if (method === 'tab') {
    tabPrompt.value = true
    return
  }
  await doCharge(method, null)
}

async function confirmTabCharge() {
  if (!tabCode.value.trim()) return
  await doCharge('tab', tabCode.value.trim())
  tabCode.value = ''
  tabPrompt.value = false
}

async function doCharge(method, code) {
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

  // Si pagó con pulsera: además emitimos tab_charge para descontar saldo.
  if (method === 'tab' && code) {
    await queueOp({
      kind: 'tab_charge',
      client_uuid: uuidv4(),
      tab_code: code,
      amount: total.value.toFixed(2),
    })
  }

  const ticketPayload = {
    venue: 'BOLICHE',
    event: ev?.name || '',
    sale: payload,
    items: cart.value.map((x) => ({ ...x })),
  }

  lastTotal.value = `${payload.total} (${method})`
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
  <div class="h-full flex flex-col">
    <div class="flex items-center justify-between bg-black border-b-2 border-line px-3 py-2 font-mono text-sm">
      <div v-if="shift" class="flex gap-3 items-center">
        <span class="text-ok">TURNO ABIERTO</span>
        <span class="text-dim">apertura ${{ shift.opening_cash }}</span>
      </div>
      <div v-else class="text-hot">TURNO CERRADO</div>
      <div class="flex gap-2">
        <button v-if="!shift" class="btn btn-ok py-1 px-2" @click="showOpen = true">ABRIR</button>
        <button v-else class="btn btn-hot py-1 px-2" @click="showClose = true">CERRAR</button>
      </div>
    </div>

    <div class="flex-1 flex flex-col md:flex-row min-h-0">
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
          <div class="grid grid-cols-3 gap-2">
            <button class="btn btn-hot" :disabled="paying || !cart.length" @click="charge('cash')">
              EFECTIVO
            </button>
            <button class="btn btn-ok" :disabled="paying || !cart.length" @click="charge('card')">
              TARJETA
            </button>
            <button class="btn btn-ok" :disabled="paying || !cart.length" @click="charge('tab')">
              PULSERA
            </button>
          </div>
          <div v-if="lastTotal" class="mt-3 bg-ok text-black font-display text-center p-2">
            COBRADO ${{ lastTotal }}
          </div>
        </div>
      </div>
    </div>

    <div v-if="showOpen" class="modal">
      <div class="modal-box">
        <div class="font-display text-xl mb-3">ABRIR TURNO</div>
        <label class="text-dim font-mono text-xs block mb-1">EFECTIVO INICIAL</label>
        <input v-model="openingCash" class="input w-full mb-3" />
        <div class="grid grid-cols-2 gap-2">
          <button class="btn btn-dim" @click="showOpen = false">CANCELAR</button>
          <button class="btn btn-ok" @click="doOpenShift">ABRIR</button>
        </div>
      </div>
    </div>

    <div v-if="showClose" class="modal">
      <div class="modal-box">
        <div class="font-display text-xl mb-3">CERRAR TURNO</div>
        <label class="text-dim font-mono text-xs block mb-1">EFECTIVO DECLARADO</label>
        <input v-model="closingCash" class="input w-full mb-3" />
        <label class="text-dim font-mono text-xs block mb-1">NOTAS</label>
        <input v-model="closeNotes" class="input w-full mb-3" />
        <div class="grid grid-cols-2 gap-2">
          <button class="btn btn-dim" @click="showClose = false">CANCELAR</button>
          <button class="btn btn-hot" @click="doCloseShift">CERRAR</button>
        </div>
      </div>
    </div>

    <div v-if="tabPrompt" class="modal">
      <div class="modal-box">
        <div class="font-display text-xl mb-3">COBRAR PULSERA</div>
        <label class="text-dim font-mono text-xs block mb-1">CÓDIGO PULSERA</label>
        <input v-model="tabCode" class="input w-full mb-3" autofocus @keyup.enter="confirmTabCharge" />
        <div class="text-dim font-mono text-xs mb-3">TOTAL ${{ total.toFixed(0) }}</div>
        <div class="grid grid-cols-2 gap-2">
          <button class="btn btn-dim" @click="tabPrompt = false">CANCELAR</button>
          <button class="btn btn-ok" @click="confirmTabCharge">COBRAR</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.modal {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.85);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
}
.modal-box {
  background: #0a0a0a;
  border: 2px solid var(--line, #333);
  padding: 1.5rem;
  width: min(480px, 92vw);
}
.input {
  background: #000;
  border: 2px solid #333;
  padding: 0.6rem;
  font-family: ui-monospace, monospace;
  color: #fff;
  font-size: 1.1rem;
}
</style>
