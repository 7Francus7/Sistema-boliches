<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useSession } from '../stores/session.js'

const email = ref('admin@demo.local')
const password = ref('admin123')
const error = ref('')
const loading = ref(false)
const session = useSession()
const router = useRouter()

async function submit() {
  error.value = ''
  loading.value = true
  try {
    await session.login(email.value, password.value)
    await session.bootstrap()
    router.push('/')
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="flex items-center justify-center h-full p-6">
    <div class="tile w-full max-w-md p-8">
      <h1 class="font-display text-3xl mb-6">INGRESO</h1>

      <label class="block text-dim text-sm mb-1 font-mono">USUARIO</label>
      <input v-model="email" class="w-full bg-black border-2 border-line text-ink p-4 text-lg mb-4" />

      <label class="block text-dim text-sm mb-1 font-mono">CLAVE</label>
      <input v-model="password" type="password" class="w-full bg-black border-2 border-line text-ink p-4 text-lg mb-4" />

      <button class="btn btn-hot w-full" :disabled="loading" @click="submit">
        {{ loading ? 'ENTRANDO...' : 'ENTRAR' }}
      </button>

      <div v-if="error" class="mt-4 bg-danger text-white p-3 font-mono text-sm">{{ error }}</div>

      <div class="mt-6 text-dim text-xs font-mono leading-5">
        DEMO:<br />
        admin@demo.local / admin123<br />
        cajero@demo.local / cajero123<br />
        puerta@demo.local / puerta123
      </div>
    </div>
  </div>
</template>
