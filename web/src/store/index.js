import { createStore } from 'vuex'
import router from '@/router'
import axios from 'axios'

export default createStore({
  state: {
    apiBaseUrl: 'http://localhost:5300/api/v1',
    autoRefreshLog: false,
    autoScrollLog: true,
    settingsPageTab: '',
    version: 'v0.0.0',
    debug: false,
    enabledPlatformCount: 0,
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
    }
  },
  actions: {},
})
