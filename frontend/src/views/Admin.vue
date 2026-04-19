<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../api.js'

const data = ref(null)
const error = ref('')

onMounted(async () => {
  try {
    data.value = await api.dashboard()
  } catch (e) {
    error.value = e.message
  }
})
</script>

<template>
  <div class="p-6">
    <div class="flex items-center justify-between mb-6">
      <h1 class="font-display text-3xl">DASHBOARD</h1>
      <router-link to="/admin/stock" class="btn btn-hot px-6 py-3">STOCK Y PRECIOS</router-link>
    </div>

    <div v-if="error" class="bg-danger text-white p-3 font-mono text-sm">{{ error }}</div>

    <div v-if="data" class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
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
    </div>

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
  </div>
</template>
