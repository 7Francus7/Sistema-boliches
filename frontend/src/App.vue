<script setup>
import { onMounted, ref } from 'vue'
import { useSession } from './stores/session.js'
import { outboxCount, drainOnce } from './sync/engine.js'

const session = useSession()
const online = ref(navigator.onLine)
const pending = ref(0)

onMounted(async () => {
  await session.restore()
  window.addEventListener('online', () => (online.value = true))
  window.addEventListener('offline', () => (online.value = false))
  setInterval(async () => {
    pending.value = await outboxCount()
  }, 1500)
})
</script>

<template>
  <div class="min-h-screen flex flex-col">
    <header class="bg-black border-b-2 border-line flex items-center justify-between px-4 py-2">
      <div class="font-display text-lg">BOLICHE · POS</div>
      <div class="flex gap-2 items-center text-sm font-mono">
        <span :class="online ? 'text-ok' : 'text-danger'">
          {{ online ? 'ONLINE' : 'OFFLINE' }}
        </span>
        <span class="text-dim">|</span>
        <span>COLA:
          <span :class="pending > 0 ? 'text-hot' : 'text-ok'">{{ pending }}</span>
        </span>
        <button v-if="pending > 0" class="kbd" @click="drainOnce">SYNC</button>
      </div>
    </header>
    <main class="flex-1">
      <router-view />
    </main>
  </div>
</template>
