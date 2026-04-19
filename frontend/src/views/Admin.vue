<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../api.js'

const data = ref(null)
const alerts = ref([])
const error = ref('')

onMounted(async () => {
  try {
    const [dash, low] = await Promise.all([api.dashboard(), api.lowStock().catch(() => [])])
    data.value = dash
    alerts.value = low || []
  } catch (e) {
    error.value = e.message
  }
})

async function downloadCsv() {
  try {
    const text = await api.salesCsv()
    const blob = new Blob([text], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `ventas-${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    error.value = e.message
  }
}
</script>

<template>
  <div class="p-6">
    <div class="flex items-center justify-between mb-6 flex-wrap gap-2">
      <h1 class="font-display text-3xl">DASHBOARD</h1>
      <div class="flex gap-2 flex-wrap">
        <router-link to="/admin/stock" class="btn btn-hot px-4 py-2">STOCK</router-link>
        <router-link to="/admin/suppliers" class="btn btn-ok px-4 py-2">PROVEEDORES</router-link>
        <router-link to="/admin/promoters" class="btn btn-ok px-4 py-2">RRPP</router-link>
        <router-link to="/admin/shifts" class="btn btn-ok px-4 py-2">TURNOS</router-link>
        <router-link to="/admin/alerts" class="btn btn-hot px-4 py-2">
          ALERTAS <span v-if="alerts.length" class="text-black bg-white px-1 ml-1">{{ alerts.length }}</span>
        </router-link>
        <button class="btn btn-dim px-4 py-2" @click="downloadCsv">CSV VENTAS</button>
      </div>
    </div>

    <div v-if="error" class="bg-danger text-white p-3 font-mono text-sm mb-4">{{ error }}</div>

    <div v-if="data" class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
      <div class="tile p-6">
        <div class="text-dim font-mono text-sm">FACTURACIÓN</div>
        <div class="font-display text-4xl text-hot">${{ Math.round(data.revenue_total).toLocaleString() }}</div>
      </div>
      <div class="tile p-6">
        <div class="text-dim font-mono text-sm">VENTAS</div>
        <div class="font-display text-4xl">{{ data.sales_count }}</div>
      </div>
      <div class="tile p-6">
        <div class="text-dim font-mono text-sm">TICKET PROMEDIO</div>
        <div class="font-display text-4xl">${{ Math.round(data.avg_ticket).toLocaleString() }}</div>
      </div>
      <div v-if="data.margin_total !== undefined" class="tile p-6">
        <div class="text-dim font-mono text-sm">MARGEN BRUTO</div>
        <div class="font-display text-4xl text-ok">${{ Math.round(data.margin_total).toLocaleString() }}</div>
      </div>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div v-if="data" class="tile p-4">
        <div class="text-dim font-mono text-sm mb-2">TOP PRODUCTOS</div>
        <table class="w-full font-mono text-sm">
          <thead class="text-dim">
            <tr>
              <th class="text-left py-1">PRODUCTO</th>
              <th class="text-right py-1">UNID.</th>
              <th class="text-right py-1">$$$</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in data.top_products" :key="p.name" class="border-t border-line">
              <td class="py-2">{{ p.name }}</td>
              <td class="py-2 text-right">{{ p.units }}</td>
              <td class="py-2 text-right text-hot">${{ Math.round(p.revenue).toLocaleString() }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="data && data.top_cashiers" class="tile p-4">
        <div class="text-dim font-mono text-sm mb-2">RANKING CAJEROS</div>
        <table class="w-full font-mono text-sm">
          <thead class="text-dim">
            <tr>
              <th class="text-left py-1">CAJERO</th>
              <th class="text-right py-1">VENTAS</th>
              <th class="text-right py-1">$$$</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="c in data.top_cashiers" :key="c.email" class="border-t border-line">
              <td class="py-2">{{ c.email }}</td>
              <td class="py-2 text-right">{{ c.count }}</td>
              <td class="py-2 text-right text-hot">${{ Math.round(c.revenue).toLocaleString() }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
