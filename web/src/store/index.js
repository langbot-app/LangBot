import { createStore } from 'vuex'
import router from '@/router'
import axios from 'axios'

export default createStore({
  state: {
    apiBaseUrl: 'http://localhost:5300/api/v1',
    autoRefreshLog: false,
    version: '0.0.1'
  },
  mutations: {},
  actions: {},
})
