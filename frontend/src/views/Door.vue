<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { BrowserMultiFormatReader } from '@zxing/browser'
import { db, getKV } from '../db.js'
import { queueOp, uuidv4, drainOnce } from '../sync/engine.js'

const status = ref('idle') // idle | ok | bad | used | scanning
const message = ref('APUNTAR QR')
const count = ref(0)
const capacity = ref(500)
const videoRef = ref(null)

let reader = null
let lastHandled = null

async function refreshCount() {
  const logs = await db.access_local.toArray()
  count.value = logs.filter(l => l.direction === 'in').length
}

async function handleCode(text) {
  if (!text || text === lastHandled) return
  lastHandled = text
  setTimeout(() => (lastHandled = null), 1200)

  const ticket = await db.tickets.where('qr_code').equals(text).first()
  if (!ticket) {
    return flash('bad', 'INVÁLIDO')
  }
  if (ticket.status === 'used') {
    return flash('used', 'YA USADO')
  }
  if (ticket.status === 'void') {
    return flash('bad', 'ANULADO')
  }

  // Marcar localmente como usado.
  await db.tickets.update(ticket.id, { status: 'used' })
  const clientUuid = uuidv4()
  const deviceId = await getKV('device_id')
  const ev = await db.event.toCollection().first()
  const scannedAt = new Date().toISOString()

  await db.access_local.put({
    client_uuid: clientUuid,
    ticket_id: ticket.id,
    event_id: ev?.id,
    direction: 'in',
    scanned_at: scannedAt,
    synced: 0,
  })

  await queueOp({
    kind: 'access',
    client_uuid: clientUuid,
    ticket_id: ticket.id,
    event_id: ev?.id,
    device_id: deviceId,
    direction: 'in',
    scanned_at: scannedAt,
  })

  await refreshCount()
  flash('ok', 'ADENTRO')
  drainOnce()
}

function flash(kind, text) {
  status.value = kind
  message.value = text
  setTimeout(() => {
    status.value = 'scanning'
    message.value = 'APUNTAR QR'
  }, 900)
}

onMounted(async () => {
  capacity.value = (await getKV('capacity')) || 500
  const ev = await db.event.toCollection().first()
  if (ev?.capacity) capacity.value = ev.capacity
  await refreshCount()

  try {
    reader = new BrowserMultiFormatReader()
    status.value = 'scanning'
    await reader.decodeFromVideoDevice(undefined, videoRef.value, (result) => {
      if (result) handleCode(result.getText())
    })
  } catch (e) {
    message.value = 'SIN CÁMARA'
    status.value = 'bad'
  }
})

onBeforeUnmount(() => {
  try { reader && BrowserMultiFormatReader.releaseAllStreams() } catch {}
})

const bgClass = {
  idle: 'bg-black',
  scanning: 'bg-black',
  ok: 'bg-ok',
  bad: 'bg-danger',
  used: 'bg-hot',
}
</script>

<template>
  <div class="h-full grid grid-rows-[auto_1fr_auto]">
    <div class="p-3 flex justify-between border-b-2 border-line font-mono text-sm">
      <div>AFORO: <span class="text-hot">{{ count }}</span> / {{ capacity }}</div>
      <div>{{ Math.round((count / capacity) * 100) }}%</div>
    </div>

    <div class="relative flex items-center justify-center" :class="bgClass[status]">
      <video ref="videoRef" class="absolute inset-0 w-full h-full object-cover opacity-40" playsinline muted />
      <div class="relative font-display text-5xl md:text-7xl text-white drop-shadow text-center px-6">
        {{ message }}
      </div>
    </div>

    <div class="p-3 border-t-2 border-line font-mono text-xs text-dim text-center">
      Alineá el QR en la cámara. Beep = adentro. Rojo = rechazo.
    </div>
  </div>
</template>
