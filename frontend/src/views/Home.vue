<script setup>
import { useSession } from '../stores/session.js'
const session = useSession()
</script>

<template>
  <div class="p-6">
    <div class="mb-6 tile p-4">
      <div class="text-dim text-sm font-mono">EVENTO ACTIVO</div>
      <div class="font-display text-2xl">
        {{ session.event?.name || 'SIN EVENTO CARGADO' }}
      </div>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
      <router-link to="/pos" class="btn btn-hot text-center block">POS / BARRA</router-link>
      <router-link to="/door" class="btn btn-ok text-center block">PUERTA / QR</router-link>
      <router-link to="/admin" class="btn text-center block">DASHBOARD</router-link>
    </div>

    <button class="btn btn-danger mt-8" @click="session.logout().then(() => location.reload())">
      SALIR
    </button>
  </div>
</template>
