<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../api.js'

const list = ref([])
const commissions = ref([])
const form = ref({ name: '', phone: '', commission_pct: '10' })
const error = ref('')

async function refresh() {
  try {
    const [ps, cs] = await Promise.all([api.listPromoters(), api.commissions().catch(() => [])])
    list.value = ps
    commissions.value = cs
  } catch (e) {
    error.value = e.message
  }
}

async function create() {
  try {
    await api.createPromoter({ ...form.value })
    form.value = { name: '', phone: '', commission_pct: '10' }
    await refresh()
  } catch (e) {
    error.value = e.message
  }
}

async function toggle(p) {
  try {
    await api.togglePromoter(p.id)
    await refresh()
  } catch (e) {
    error.value = e.message
  }
}

onMounted(refresh)
</script>

<template>
  <div class="p-6">
    <div class="flex justify-between items-center mb-4">
      <h1 class="font-display text-3xl">RRPP / PROMOTORES</h1>
      <router-link to="/admin" class="btn btn-dim px-3 py-2">VOLVER</router-link>
    </div>

    <div v-if="error" class="bg-danger text-white p-2 mb-3 font-mono text-sm">{{ error }}</div>

    <div class="tile p-4 mb-6">
      <div class="text-dim font-mono text-xs mb-2">NUEVO RRPP</div>
      <div class="grid grid-cols-1 md:grid-cols-4 gap-2">
        <input v-model="form.name" placeholder="Nombre" class="input" />
        <input v-model="form.phone" placeholder="Teléfono" class="input" />
        <input v-model="form.commission_pct" placeholder="% comisión" class="input" />
        <button class="btn btn-ok" @click="create">ALTA</button>
      </div>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div class="tile p-4">
        <div class="text-dim font-mono text-sm mb-2">LISTADO</div>
        <table class="w-full font-mono text-sm">
          <thead class="text-dim">
            <tr>
              <th class="text-left py-1">NOMBRE</th>
              <th class="text-right py-1">%</th>
              <th class="text-right py-1">ESTADO</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in list" :key="p.id" class="border-t border-line">
              <td class="py-2">{{ p.name }}</td>
              <td class="py-2 text-right">{{ p.commission_pct }}</td>
              <td class="py-2 text-right" :class="p.active ? 'text-ok' : 'text-dim'">
                {{ p.active ? 'ACTIVO' : 'INACTIVO' }}
              </td>
              <td class="py-2 text-right">
                <button class="btn btn-dim px-2 py-1 text-xs" @click="toggle(p)">TOGGLE</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="tile p-4">
        <div class="text-dim font-mono text-sm mb-2">LIQUIDACIÓN COMISIONES</div>
        <table class="w-full font-mono text-sm">
          <thead class="text-dim">
            <tr>
              <th class="text-left py-1">RRPP</th>
              <th class="text-right py-1">TICKETS</th>
              <th class="text-right py-1">BRUTO</th>
              <th class="text-right py-1">COMISIÓN</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="c in commissions" :key="c.promoter_id" class="border-t border-line">
              <td class="py-2">{{ c.name }}</td>
              <td class="py-2 text-right">{{ c.tickets_sold }}</td>
              <td class="py-2 text-right">${{ Math.round(c.revenue).toLocaleString() }}</td>
              <td class="py-2 text-right text-hot">${{ Math.round(c.commission_amount).toLocaleString() }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<style scoped>
.input {
  background: #000;
  border: 2px solid #333;
  padding: 0.5rem;
  font-family: ui-monospace, monospace;
  color: #fff;
}
</style>
