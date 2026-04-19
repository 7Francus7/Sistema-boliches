<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../api.js'

const alerts = ref([])
const error = ref('')

async function refresh() {
  try {
    alerts.value = await api.lowStock()
  } catch (e) {
    error.value = e.message
  }
}

onMounted(refresh)
</script>

<template>
  <div class="p-6">
    <div class="flex justify-between items-center mb-4">
      <h1 class="font-display text-3xl">ALERTAS DE STOCK</h1>
      <router-link to="/admin" class="btn btn-dim px-3 py-2">VOLVER</router-link>
    </div>

    <div v-if="error" class="bg-danger text-white p-2 mb-3 font-mono text-sm">{{ error }}</div>

    <div v-if="!alerts.length" class="tile p-6 text-center text-dim font-mono">SIN ALERTAS — STOCK OK</div>

    <div v-else class="tile p-4">
      <table class="w-full font-mono text-sm">
        <thead class="text-dim">
          <tr>
            <th class="text-left py-1">SKU</th>
            <th class="text-left py-1">PRODUCTO</th>
            <th class="text-right py-1">STOCK</th>
            <th class="text-right py-1">UMBRAL</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="a in alerts" :key="a.sku" class="border-t border-line">
            <td class="py-2">{{ a.sku }}</td>
            <td class="py-2">{{ a.name }}</td>
            <td class="py-2 text-right text-danger">{{ a.qty_on_hand }}</td>
            <td class="py-2 text-right text-dim">{{ a.threshold }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
