import { defineStore } from 'pinia'
import { api } from '../api.js'
import { db, getKV, setKV } from '../db.js'
import { uuidv4 } from '../sync/engine.js'

export const useSession = defineStore('session', {
  state: () => ({
    token: null,
    role: null,
    user_id: null,
    venue_id: null,
    device_id: null,
    event: null,
    bootstrapped: false,
  }),

  actions: {
    async restore() {
      this.token = await getKV('token')
      this.role = await getKV('role')
      this.user_id = await getKV('user_id')
      this.venue_id = await getKV('venue_id')
      this.device_id = await getKV('device_id')
      const ev = await db.event.toCollection().first()
      this.event = ev || null
      this.bootstrapped = !!ev
    },

    async login(email, password) {
      const r = await api.login(email, password)
      await setKV('token', r.access_token)
      await setKV('role', r.role)
      await setKV('user_id', r.user_id)
      await setKV('venue_id', r.venue_id)
      if (!(await getKV('device_id'))) {
        // Generamos device_id local la primera vez. En prod se registra en backend.
        await setKV('device_id', uuidv4())
      }
      await this.restore()
    },

    async bootstrap() {
      const data = await api.bootstrap()
      await db.transaction('rw', db.products, db.tickets, db.event, async () => {
        await db.products.clear()
        await db.tickets.clear()
        await db.event.clear()
        await db.products.bulkPut(data.products)
        await db.tickets.bulkPut(data.tickets)
        if (data.event) await db.event.put(data.event)
      })
      await setKV('server_time', data.server_time)
      this.event = data.event
      this.bootstrapped = true
    },

    async logout() {
      await db.kv.clear()
      this.$reset()
    },
  },
})
