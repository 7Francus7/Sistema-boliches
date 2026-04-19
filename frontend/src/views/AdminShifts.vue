<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../api.js'

const list = ref([])
const report = ref(null)
const error = ref('')

async function refresh() {
  try {
    list.value = await api.listShifts()
  } catch (e) {
    error.value = e.message
  }
}

async function openReport(id) {
  try {
    report.value = await api.shiftCloseReport(id)
  } catch (e) {
    error.value = e.message
  }
}

function fmtDate(s) {
  return s ? new Date(s).toLocaleString() : '-'
}

onMounted(refresh)
</script>

<template>
  <div class="p-6">
    <div class="flex justify-between items-center mb-4">
      <h1 class="font-display text-3xl">TURNOS</h1>
      <router-link to="/admin" class="btn btn-dim px-3 py-2">VOLVER</router-link>
    </div>

    <div v-if="error" class="bg-danger text-white p-2 mb-3 font-mono text-sm">{{ error }}</div>

    <div class="tile p-4 mb-4">
      <table class="w-full font-mono text-sm">
        <thead class="text-dim">
          <tr>
            <th class="text-left py-1">APERTURA</th>
            <th class="text-left py-1">CIERRE</th>
            <th class="text-right py-1">INICIAL</th>
            <th class="text-right py-1">ESPERADO</th>
            <th class="text-right py-1">DECLARADO</th>
            <th class="text-right py-1">VARIANCE</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="s in list" :key="s.id" class="border-t border-line">
            <td class="py-2">{{ fmtDate(s.opened_at) }}</td>
            <td class="py-2">{{ fmtDate(s.closed_at) }}</td>
            <td class="py-2 text-right">${{ s.opening_cash }}</td>
            <td class="py-2 text-right">${{ s.expected_cash ?? '-' }}</td>
            <td class="py-2 text-right">${{ s.closing_cash ?? '-' }}</td>
            <td class="py-2 text-right" :class="Number(s.cash_variance || 0) < 0 ? 'text-danger' : 'text-ok'">
              {{ s.cash_variance ?? '-' }}
            </td>
            <td class="py-2 text-right">
              <button v-if="s.closed_at" class="btn btn-dim px-2 py-1 text-xs" @click="openReport(s.id)">Z</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="report" class="tile p-4">
      <div class="flex justify-between items-center mb-2">
        <div class="text-dim font-mono text-sm">REPORTE Z · {{ report.shift_id }}</div>
        <button class="btn btn-dim px-2 py-1 text-xs" @click="report = null">X</button>
      </div>
      <div class="grid grid-cols-2 md:grid-cols-4 gap-2 mb-3 font-mono text-sm">
        <div>INICIAL: <span class="text-hot">${{ report.opening_cash }}</span></div>
        <div>ESPERADO: <span class="text-hot">${{ report.expected_cash }}</span></div>
        <div>DECLARADO: <span class="text-hot">${{ report.closing_cash }}</span></div>
        <div>VARIANCE: <span :class="report.cash_variance < 0 ? 'text-danger' : 'text-ok'">${{ report.cash_variance }}</span></div>
      </div>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <div class="text-dim font-mono text-xs mb-1">INGRESOS POR MÉTODO</div>
          <table class="w-full font-mono text-sm">
            <tr v-for="m in report.sales_by_method" :key="m.method" class="border-t border-line">
              <td class="py-1">{{ m.method.toUpperCase() }}</td>
              <td class="py-1 text-right">{{ m.count }}</td>
              <td class="py-1 text-right text-hot">${{ Math.round(m.total).toLocaleString() }}</td>
            </tr>
          </table>
        </div>
        <div>
          <div class="text-dim font-mono text-xs mb-1">PRODUCTOS VENDIDOS</div>
          <table class="w-full font-mono text-sm">
            <tr v-for="i in report.items_sold" :key="i.product" class="border-t border-line">
              <td class="py-1">{{ i.product }}</td>
              <td class="py-1 text-right">{{ i.units }}</td>
              <td class="py-1 text-right text-hot">${{ Math.round(i.revenue).toLocaleString() }}</td>
            </tr>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>
