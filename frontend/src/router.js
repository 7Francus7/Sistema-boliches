import { createRouter, createWebHistory } from 'vue-router'
import { useSession } from './stores/session.js'

const routes = [
  { path: '/login', component: () => import('./views/Login.vue') },
  { path: '/', component: () => import('./views/Home.vue') },
  { path: '/pos', component: () => import('./views/POS.vue') },
  { path: '/door', component: () => import('./views/Door.vue') },
  { path: '/admin', component: () => import('./views/Admin.vue') },
  { path: '/admin/stock', component: () => import('./views/AdminStock.vue') },
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to) => {
  const s = useSession()
  if (!s.token) await s.restore()
  if (!s.token && to.path !== '/login') return '/login'
  if (s.token && to.path === '/login') return '/'
})
