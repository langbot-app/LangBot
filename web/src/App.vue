<template>
  <v-app>
    <div v-if="shouldShowLayout" class="app">
      <div class="up">
        <header>
          <!-- 顶部导航条 -->
          <v-app-bar class="px-2" flat>
            <template v-slot:prepend>
              <v-app-bar-nav-icon @click="sidebarVisible = !sidebarVisible"></v-app-bar-nav-icon>
            </template>
            <v-toolbar-title>LangBot</v-toolbar-title>
          </v-app-bar>
        </header>
      </div>
      <div class="down">
        <div class="sidebar">
          <!-- 侧边栏 - 使用提取出来的Sidebar组件 -->
          <SidebarComponent v-model="sidebarVisible" />
        </div>
        <div class="app-main">
          <!-- 主内容区域 -->
          <v-main>
            <router-view />
          </v-main>
        </div>
      </div>
    </div>

    <!-- 当不需要Layout时直接显示路由内容 -->
    <router-view v-else />

    <!-- 全局消息通知组件 -->
    <v-snackbar v-model="snackbarVisible" :color="snackbarColor" :timeout="snackbarTimeout"
      :location="snackbarLocation">
      {{ snackbarText }}
      <template v-slot:actions>
        <v-btn color="light" variant="text" @click="snackbarVisible = false">
          关闭
        </v-btn>
      </template>
    </v-snackbar>
  </v-app>
</template>

<script setup>
import { computed, onMounted, provide, ref } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useStore } from 'vuex';
import SidebarComponent from '@/components/layout/Sidebar.vue';

const router = useRouter();
const route = useRoute();
const store = useStore();

const sidebarVisible = ref(true);

// Snackbar组件数据
const snackbarVisible = ref(false);
const snackbarText = ref('');
const snackbarColor = ref('success'); // success, info, warning, error
const snackbarTimeout = ref(3000);
const snackbarLocation = ref('top');

// 提供snackbar服务给所有子组件使用
provide('snackbar', {
  success: message => showSnackbar(message, 'success'),
  info: message => showSnackbar(message, 'info'),
  warning: message => showSnackbar(message, 'warning'),
  error: message => showSnackbar(message, 'error')
});

// 辅助函数：显示消息通知
function showSnackbar(text, color = 'success', timeout = 3000, location = 'top') {
  snackbarText.value = text;
  snackbarColor.value = color;
  snackbarTimeout.value = timeout;
  snackbarLocation.value = location;
  snackbarVisible.value = true;
}

// 系统重载功能
async function reload(scope) {
  try {
    await store.dispatch('reloadSystem', { scope });
    showSnackbar(`已重新加载${scope === 'platform' ? '消息平台' : scope === 'plugin' ? '插件' : 'LLM 管理器'}`, 'success');
  } catch (error) {
    showSnackbar(`重新加载失败: ${error.message}`, 'error');
  }
}

// 检查是否需要显示Layout（路由是否为登录或初始化页面）
const shouldShowLayout = computed(() => {
  return !['/login', '/init'].includes(route.path);
});

// 组件加载后初始化操作
onMounted(async () => {
  // 检查令牌有效性
  await store.dispatch('checkTokenValidity');

  // 获取系统信息
  store.commit('fetchSystemInfo');
});
</script>

<style scoped>
.app {
  display: flex;
  flex-direction: column;
  height: 100vh;
}

.up {
  width: 100%;
}

.down {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.sidebar {
  height: 100%;
}

.app-main {
  flex: 1;
  overflow-y: auto;
}

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
