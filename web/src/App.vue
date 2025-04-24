<template>
  <v-app>
    <v-snackbar v-model="snackbar" :color="color" :timeout="timeout" :location="location">
      {{ text }}
    </v-snackbar>

    <div id="app-container" v-if="proxy.$store.state.user.tokenChecked && proxy.$store.state.user.tokenValid">
      <v-layout class="flex-layout">
        <Sidebar :version="proxy.$store.state.version" :debug="proxy.$store.state.debug" @reload="reload"
          @logout="logout" @openDocs="openDocs" />

        <v-main class="content-area">
          <router-view />
        </v-main>
      </v-layout>
    </div>

    <div id="loading-container" v-if="!proxy.$store.state.user.tokenChecked">
      <div id="loading-text">
        <img src="@/assets/langbot-logo.png" height="32" width="32" />
        <span id="loading-text-span">正在加载...</span>
      </div>
    </div>

    <div id="login-container"
      v-if="proxy.$store.state.user.tokenChecked && !proxy.$store.state.user.tokenValid && proxy.$store.state.user.systemInitialized">
      <LoginDialog @error="error" @success="success" @checkToken="checkToken" />
    </div>

    <div id="uninitialized-container"
      v-if="proxy.$store.state.user.tokenChecked && !proxy.$store.state.user.systemInitialized">
      <InitDialog @error="error" @success="success" @checkSystemInitialized="checkSystemInitialized" />
    </div>
  </v-app>
</template>

<script setup>
import { getCurrentInstance } from 'vue'
import { provide, ref, onMounted } from 'vue';

import Sidebar from '@/components/layout/Sidebar.vue';
import TaskDialog from '@/components/TaskListDialog.vue';
import AboutDialog from '@/components/AboutDialog.vue';
import InitDialog from '@/components/InitDialog.vue';
import LoginDialog from '@/components/LoginDialog.vue';

const { proxy } = getCurrentInstance()

const snackbar = ref(false);
const color = ref('success');
const text = ref('');
const location = ref('top');
const timeout = ref(2000);

function success(content) {
  snackbar.value = true;
  color.value = 'success';
  text.value = content;
}

function error(content) {
  snackbar.value = true;
  color.value = 'error';
  text.value = content;
}

function warning(content) {
  snackbar.value = true;
  color.value = 'warning';
  text.value = content;
}

function info(content) {
  snackbar.value = true;
  color.value = 'primary';
  text.value = content;
}

provide('snackbar', { success, error, warning, info, location, timeout });

function openDocs() {
  window.open('https://docs.langbot.app', '_blank')
}

const reloadScopeLabel = {
  'platform': "消息平台",
  'plugin': "插件",
  'provider': "LLM 管理器"
}

function reload(scope) {
  let label = reloadScopeLabel[scope]
  proxy.$axios.post('/system/reload',
    { scope: scope },
    { headers: { 'Content-Type': 'application/json' } }
  ).then(response => {
    if (response.data.code === 0) {
      success(label + '已重载')
    } else {
      error(label + '重载失败：' + response.data.message)
    }
  }).catch(err => {
    error(label + '重载失败：' + err)
  })
}

function checkSystemInitialized() {
  proxy.$axios.get('/user/init').then(response => {
    if (response.data.code === 0) {
      proxy.$store.state.user.systemInitialized = response.data.data.initialized
    } else {
      error('系统初始化状态检查失败：' + response.data.message)
      proxy.$store.state.user.systemInitialized = true
    }

    checkToken()
  }).catch(err => {
    error('系统初始化状态检查失败：' + err)
    proxy.$store.state.user.systemInitialized = true
  })
}

function checkToken() {
  proxy.$axios.get('/user/check-token').then(response => {
    if (response.data.code === 0) {
      proxy.$store.state.user.tokenValid = true
    } else {
      proxy.$store.state.user.tokenValid = false
    }
  }).catch(err => {
    proxy.$store.state.user.tokenValid = false
  }).finally(() => {
    proxy.$store.state.user.tokenChecked = true
  })
}

function logout() {
  proxy.$store.dispatch('user/logout').then(() => {
    proxy.$router.push('/login')
  }).catch(err => {
    error('退出登录失败：' + err)
  })
}

onMounted(() => {
  checkSystemInitialized()
})
</script>

<style scoped>
#app-container {
  display: flex;
  height: 100vh;
}

.flex-layout {
  display: flex;
  width: 100%;
}

.content-area {
  flex: 1;
  background-color: #f6f6f6;
  overflow-y: auto;
}

#loading-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  user-select: none;
}

#loading-text {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

#loading-text-span {
  font-size: 1.2rem;
  font-weight: 500;
  padding-top: 0.2rem;
}
</style>
