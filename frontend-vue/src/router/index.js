import { createRouter, createWebHistory } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getMe } from '../services/auth'
import LoginView from '../views/LoginView.vue'
import ItemsView from '../views/ItemsView.vue'
import DashboardView from '../views/DashboardView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: LoginView },
    { path: '/', redirect: '/dashboard' },
    { path: '/dashboard', name: 'dashboard', component: DashboardView, meta: { requiresAuth: true } },
    { path: '/items', name: 'items', component: ItemsView, meta: { requiresAuth: true } },
  ],
})

router.beforeEach(async (to, _from, next) => {
  if (!to.meta.requiresAuth) {
    next()
    return
  }
  try {
    await getMe()
    next()
  } catch {
    ElMessage.warning('请先登录')
    next('/login')
  }
})

export default router
