/**
 * plugins/index.js
 *
 * Automatically included in `./src/main.js`
 */

// Plugins
import vuetify from './vuetify'
import router from '@/router'
import store from '@/store'
import axios from 'axios'

export function registerPlugins (app) {
  app
    .use(vuetify)
    .use(router)
    .use(store)

  // 读取用户令牌
  const token = localStorage.getItem('user-token')

  if (token) {
    store.state.user.jwtToken = token
  }

  // 所有axios请求均携带用户令牌
  axios.defaults.headers.common['Authorization'] = `Bearer ${store.state.user.jwtToken}`

  app.config.globalProperties.$axios = axios
  store.commit('initializeFetch')
}
