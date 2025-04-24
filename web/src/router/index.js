/**
 * router/index.ts
 *
 * Automatic routes for `./src/pages/*.vue`
 */

// Composables
import { createRouter, createWebHashHistory } from 'vue-router/auto'
import DashBoard from '../pages/DashBoard.vue'
import Settings from '../pages/Settings.vue'
import Logs from '../pages/Logs.vue'
import Plugins from '../pages/Plugins.vue'
import Auth from '../components/Auth.vue'

const routes = [
  { path: '/', component: DashBoard, meta: { requiresAuth: true } },
  { path: '/settings', component: Settings, meta: { requiresAuth: true } },
  { path: '/logs', component: Logs, meta: { requiresAuth: true } },
  { path: '/plugins', component: Plugins, meta: { requiresAuth: true } },
  { path: '/init', component: Auth },
  { path: '/login', component: Auth },
  { path: '/auth', component: Auth, redirect: '/login' }, // 添加一个默认的 auth 路径，重定向到 login
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

// 全局路由守卫，检查用户是否已登录
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('user-token')
  const isSystemInitialized = localStorage.getItem('system-initialized') === 'true'

  // 如果系统未初始化，重定向到初始化页面
  if (!isSystemInitialized && to.path !== '/init') {
    next('/init')
    return
  }

  // 如果路由需要认证且没有token，重定向到登录页面
  if (to.meta.requiresAuth && !token) {
    next('/login')
    return
  }

  // 如果已登录但访问登录页，重定向到首页
  if (to.path === '/login' && token) {
    next('/')
    return
  }

  // 其他情况正常导航
  next()
})

// Workaround for https://github.com/vitejs/vite/issues/11804
router.onError((err, to) => {
  if (err?.message?.includes?.('Failed to fetch dynamically imported module')) {
    if (!localStorage.getItem('vuetify:dynamic-reload')) {
      console.log('Reloading page to fix dynamic import error')
      localStorage.setItem('vuetify:dynamic-reload', 'true')
      location.assign(to.fullPath)
    } else {
      console.error('Dynamic import error, reloading page did not fix it', err)
    }
  } else {
    console.error(err)
  }
})

router.isReady().then(() => {
  localStorage.removeItem('vuetify:dynamic-reload')
})

export default router
