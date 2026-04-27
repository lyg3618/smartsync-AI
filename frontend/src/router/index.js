import { createRouter, createWebHistory } from 'vue-router'
import Login from '../views/Login.vue'
import Dashboard from '../views/Dashboard.vue'
import MeetingDetail from '../views/MeetingDetail.vue'
import Todos from '../views/Todos.vue'
import Settings from '../views/Settings.vue'
import Search from '../views/Search.vue'
import Messages from '../views/Messages.vue'

const routes = [
  { path: '/', redirect: '/login' },
  { path: '/login', component: Login },
  { path: '/dashboard', component: Dashboard, meta: { requiresAuth: true } },
  { path: '/search', component: Search, meta: { requiresAuth: true } },
  { path: '/meetings/:id', component: MeetingDetail, meta: { requiresAuth: true } },
  { path: '/todos', component: Todos, meta: { requiresAuth: true } },
  { path: '/messages', component: Messages, meta: { requiresAuth: true } },
  { path: '/settings', component: Settings, meta: { requiresAuth: true } },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const token = localStorage.getItem('smartsync_token')
  if (to.meta.requiresAuth && !token) return '/login'
})

export default router
