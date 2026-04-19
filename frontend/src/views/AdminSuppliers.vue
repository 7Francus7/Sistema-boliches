<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../api.js'

const suppliers = ref([])
const products = ref([])
const purchases = ref([])
const form = ref({ name: '', contact: '', phone: '' })
const purchase = ref({ supplier_id: '', reference: '', items: [{ product_id: '', qty: 1, unit_cost: '0' }] })
const error = ref('')

async function refresh() {
  try {
    const [sups, prods, purs] = await Promise.all([
      api.listSuppliers(),
      api.listProducts(),
      api.listPurchases().catch(() => []),
    ])
    suppliers.value = sups
    products.value = prods
    purchases.value = purs
    if (!purchase.value.supplier_id && sups.length) purchase.value.supplier_id = sups[0].id
    if (!purchase.value.items[0].product_id && prods.length) purchase.value.items[0].product_id = prods[0].id
  } catch (e) {
    error.value = e.message
  }
}

async function createSupplier() {
  try {
    await api.createSupplier({ ...form.value })
    form.value = { name: '', contact: '', phone: '' }
    await refresh()
  } catch (e) {
    error.value = e.message
  }
}

function addLine() {
  purchase.value.items.push({ product_id: products.value[0]?.id || '', qty: 1, unit_cost: '0' })
}

function removeLine(i) {
  purchase.value.items.splice(i, 1)
}

async function registerPurchase() {
  try {
    await api.createPurchase({
      supplier_id: purchase.value.supplier_id,
      reference: purchase.value.reference,
      items: purchase.value.items.map((x) => ({
        product_id: x.product_id,
        qty: Number(x.qty),
        unit_cost: String(x.unit_cost),
      })),
    })
    purchase.value = {
      supplier_id: suppliers.value[0]?.id || '',
      reference: '',
      items: [{ product_id: products.value[0]?.id || '', qty: 1, unit_cost: '0' }],
    }
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
      <h1 class="font-display text-3xl">PROVEEDORES / COMPRAS</h1>
      <router-link to="/admin" class="btn btn-dim px-3 py-2">VOLVER</router-link>
    </div>

    <div v-if="error" class="bg-danger text-white p-2 mb-3 font-mono text-sm">{{ error }}</div>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
      <div class="tile p-4">
        <div class="text-dim font-mono text-sm mb-2">NUEVO PROVEEDOR</div>
        <div class="grid grid-cols-1 gap-2">
          <input v-model="form.name" placeholder="Razón social" class="input" />
          <input v-model="form.contact" placeholder="Contacto" class="input" />
          <input v-model="form.phone" placeholder="Teléfono" class="input" />
          <button class="btn btn-ok" @click="createSupplier">ALTA</button>
        </div>
      </div>

      <div class="tile p-4">
        <div class="text-dim font-mono text-sm mb-2">LISTADO</div>
        <table class="w-full font-mono text-sm">
          <tr v-for="s in suppliers" :key="s.id" class="border-t border-line">
            <td class="py-2">{{ s.name }}</td>
            <td class="py-2 text-right text-dim">{{ s.contact }}</td>
          </tr>
        </table>
      </div>
    </div>

    <div class="tile p-4 mb-4">
      <div class="text-dim font-mono text-sm mb-2">REGISTRAR COMPRA</div>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-2 mb-2">
        <select v-model="purchase.supplier_id" class="input">
          <option v-for="s in suppliers" :key="s.id" :value="s.id">{{ s.name }}</option>
        </select>
        <input v-model="purchase.reference" placeholder="Nº remito" class="input" />
        <button class="btn btn-dim" @click="addLine">+ ÍTEM</button>
      </div>
      <div v-for="(it, i) in purchase.items" :key="i" class="grid grid-cols-1 md:grid-cols-4 gap-2 mb-2">
        <select v-model="it.product_id" class="input">
          <option v-for="p in products" :key="p.id" :value="p.id">{{ p.name }} ({{ p.sku }})</option>
        </select>
        <input v-model="it.qty" type="number" min="1" placeholder="Cantidad" class="input" />
        <input v-model="it.unit_cost" placeholder="Costo unit." class="input" />
        <button class="btn btn-hot" @click="removeLine(i)">QUITAR</button>
      </div>
      <button class="btn btn-ok w-full" @click="registerPurchase">REGISTRAR COMPRA</button>
    </div>

    <div class="tile p-4">
      <div class="text-dim font-mono text-sm mb-2">COMPRAS RECIENTES</div>
      <table class="w-full font-mono text-sm">
        <thead class="text-dim">
          <tr>
            <th class="text-left py-1">FECHA</th>
            <th class="text-left py-1">REMITO</th>
            <th class="text-right py-1">TOTAL</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in purchases" :key="p.id" class="border-t border-line">
            <td class="py-2">{{ new Date(p.received_at).toLocaleDateString() }}</td>
            <td class="py-2">{{ p.reference || '-' }}</td>
            <td class="py-2 text-right text-hot">${{ Math.round(p.total).toLocaleString() }}</td>
          </tr>
        </tbody>
      </table>
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
