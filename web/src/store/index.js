import { createStore } from 'vuex'
import router from '@/router'
import axios from 'axios'

export default createStore({
  state: {
    // 开发时使用
    apiBaseUrl: 'http://localhost:5300/api/v1',
    // apiBaseUrl: '/api/v1',
    autoRefreshLog: false,
    autoScrollLog: true,
    settingsPageTab: '',
    version: 'v0.0.0',
    debug: false,
    enabledPlatformCount: 0,
    user: {
      tokenChecked: false,
      tokenValid: false,
      systemInitialized: true,
      jwtToken: '',
    },
    pluginsView: 'installed',
    marketplaceParams: {
      query: '',
      page: 1,
      per_page: 10,
      sort_by: 'pushed_at',
      sort_order: 'DESC',
    },
    marketplacePlugins: [],
    marketplaceTotalPages: 0,
    marketplaceTotalPluginsCount: 0,
  },
  mutations: {
    initializeFetch() {
      axios.defaults.baseURL = this.state.apiBaseUrl

      axios.get('/system/info').then(response => {
        this.state.version = response.data.data.version
        this.state.debug = response.data.data.debug
        this.state.enabledPlatformCount = response.data.data.enabled_platform_count
      })
    },
    fetchSystemInfo() {
      axios.get('/system/info').then(response => {
        this.state.version = response.data.data.version
        this.state.debug = response.data.data.debug
        this.state.enabledPlatformCount = response.data.data.enabled_platform_count
      })
    },
    setUserToken(state, token) {
      state.user.jwtToken = token
    },
    setTokenValid(state, isValid) {
      state.user.tokenValid = isValid
    },
    setTokenChecked(state, isChecked) {
      state.user.tokenChecked = isChecked
    },
    setSystemInitialized(state, isInitialized) {
      state.user.systemInitialized = isInitialized
    },
    clearUserData(state) {
      state.user.jwtToken = ''
      state.user.tokenValid = false
      localStorage.removeItem('user-token')
    }
  },
  actions: {
    async logout({ commit }) {
      commit('clearUserData')
      axios.defaults.headers.common['Authorization'] = ''
      router.push('/login')
    },
    async checkTokenValidity({ state, commit }) {
      if (!state.user.jwtToken) {
        commit('setTokenValid', false)
        commit('setTokenChecked', true)
        return false
      }

      try {
        const response = await axios.get('/user/check-token')
        const isValid = response.data.code === 0
        commit('setTokenValid', isValid)
        commit('setTokenChecked', true)
        return isValid
      } catch (error) {
        commit('setTokenValid', false)
        commit('setTokenChecked', true)
        return false
      }
    },
    // 添加系统重载功能
    async reloadSystem({ commit }, { scope }) {
      try {
        const response = await axios.post('/system/reload', { scope })
        if (response.data.code === 0) {
          // 重新获取系统信息
          commit('fetchSystemInfo')
          return true
        } else {
          throw new Error(response.data.msg || '重载失败')
        }
      } catch (error) {
        console.error('系统重载失败:', error)
        throw error
      }
    }
  },
  modules: {
    user: {
      namespaced: true,
      actions: {
        async logout({ rootState }) {
          try {
            // 不调用后端API，只在前端处理登出逻辑

            // 清除本地存储的token
            localStorage.removeItem('user-token')

            // 更新状态
            rootState.user.jwtToken = ''
            rootState.user.tokenValid = false

            // 更新请求头
            axios.defaults.headers.common['Authorization'] = ''

            return Promise.resolve()
          } catch (error) {
            return Promise.reject(error)
          }
        }
      }
    }
  },
})
