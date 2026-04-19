<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../api.js'

const products = ref([])
const error = ref('')
const creating = ref(false)

const form = ref({
  sku: '',
  name: '',
  category: 'barra',
  sale_price: '',
  cost_price: '',
  initial_stock: 0,
})

async function load() {
  try {
    products.value = await api.listProducts()
  } catch (e) {
    error.value = e.message
  }
}

async function create() {
  try {
    creating.value = true
    await api.createProduct({
      ...form.value,
      sale_price: String(form.value.sale_price),
      cost_price: String(form.value.cost_price || 0),
      initial_stock: Number(form.value.initial_stock || 0),
    })
    form.value = { sku: '', name: '', category: 'barra', sale_price: '', cost_price: '', initial_stock: 0 }
    await load()
  } catch (e) {
    error.value = e.message
  } finally {
    creating.value = false
  }
}

async function adjust(p, delta) {
  const reason = delta > 0 ? 'ingreso' : 'merma'
  try {
    const updated = await api.adjustStock(p.id, delta, reason)
    p.qty_on_hand = updated.qty_on_hand
  } catch (e) {
    error.value = e.message
  }
}

async function saveRow(p) {
  try {
    const updated = await api.updateProduct(p.id, {
      sku: p.sku,
      name: p.name,
      category: p.category,
      sale_price: String(p.sale_price),
      cost_price: String(p.cost_price || 0),
      initial_stock: 0,
    })
    p.sale_price = updated.sale_price
    p.edited = false
  } catch (e) {
    error.value = e.message
  }
}

onMounted(load)
</script>

<template>
  <div class="p-6">
    <h1 class="font-display text-3xl mb-4">STOCK Y PRECIOS</h1>

    <div v-if="error" class="bg-danger text-white p-3 font-mono text-sm mb-4">{{ error }}</div>

    <!-- Alta -->
    <div class="tile p-4 mb-6">
      <div class="text-dim font-mono text-sm mb-3">ALTA DE PRODUCTO</div>
      <div class="grid grid-cols-1 md:grid-cols-6 gap-2">
        <input v-model="form.sku" placeholder="SKU" class="bg-black border-2 border-line text-ink p-3" />
        <input v-model="form.name" placeholder="NOMBRE" class="bg-black border-2 border-line text-ink p-3 md:col-span-2" />
        <input v-model="form.sale_price" type="number" placeholder="PRECIO" class="bg-black border-2 border-line text-ink p-3" />
        <input v-model="form.cost_price" type="number" placeholder="COSTO" class="bg-black border-2 border-line text-ink p-3" />
        <input v-model="form.initial_stock" type="number" placeholder="STOCK" class="bg-black border-2 border-line text-ink p-3" />
      </div>
      <button class="btn btn-hot mt-3" :disabled="creating || !form.sku || !form.name || !form.sale_price" @click="create">
        {{ creating ? 'CREANDO...' : 'AGREGAR' }}
      </button>
    </div>

    <!-- Listado -->
    <div class="tile p-0 overflow-auto">
      <table class="w-full font-mono text-sm">
        <thead class="text-dim bg-black">
          <tr>
            <th class="text-left p-3">SKU</th>
            <th class="text-left p-3">NOMBRE</th>
            <th class="text-left p-3">CAT.</th>
            <th class="text-right p-3">PRECIO</th>
            <th class="text-right p-3">STOCK</th>
            <th class="p-3">AJUSTES</th>
            <th class="p-3"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in products" :key="p.id" class="border-t border-line">
            <td class="p-3"><input v-model="p.sku" @input="p.edited = true" class="bg-transparent w-24" /></td>
            <td class="p-3"><input v-model="p.name" @input="p.edited = true" class="bg-transparent w-full" /></td>
            <td class="p-3"><input v-model="p.category" @input="p.edited = true" class="bg-transparent w-20" /></td>
            <td class="p-3 text-right">
              <input v-model="p.sale_price" @input="p.edited = true" type="number"
                     class="bg-transparent w-24 text-right text-hot font-display" />
            </td>
            <td class="p-3 text-right font-display text-lg"
                :class="p.qty_on_hand < 10 ? 'text-danger' : p.qty_on_hand < 30 ? 'text-hot' : 'text-ink'">
              {{ p.qty_on_hand }}
            </td>
            <td class="p-3">
              <div class="flex gap-1 flex-wrap">
                <button class="kbd" @click="adjust(p, +10)">+10</button>
                <button class="kbd" @click="adjust(p, +1)">+1</button>
                <button class="kbd" @click="adjust(p, -1)">-1</button>
                <button class="kbd" @click="adjust(p, -10)">-10</button>
              </div>
            </td>
            <td class="p-3">
              <button v-if="p.edited" class="btn btn-ok px-3 py-2 text-sm" @click="saveRow(p)">GUARDAR</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
