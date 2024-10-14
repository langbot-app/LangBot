import { createStore } from 'vuex'
import router from '@/router'
import axios from 'axios'

export default createStore({
  state: {
    apiBaseUrl: 'http://localhost:5300/api/v1',
    autoRefreshLog: false,
    version: 'v0.0.0',
    debug: false
  },
  mutations: {
    initializeFetch() {
      axios.defaults.baseURL = this.state.apiBaseUrl

      axios.get('/system/info').then(response => {
        this.state.version = response.data.data.version
        this.state.debug = response.data.data.debug
      })
    }
  },
  actions: {},
})
