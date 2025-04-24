<template>
  <PageTitle title="设置" @refresh="refreshManagers" />

  <v-card id="settings-card" :loading="loading" class="d-flex flex-column">
    <v-tabs id="settings-tabs" v-model="activeTab" show-arrows center-active color="primary"
      @update:model-value="onTabChange">
      <v-tooltip v-for="manager in managerList" :key="manager.name" :text="manager.description" location="top">
        <template v-slot:activator="{ props }">
          <v-tab v-bind="props" :value="manager.name" style="text-transform: none;">
            {{ manager.name }}
          </v-tab>
        </template>
      </v-tooltip>
    </v-tabs>

    <v-divider></v-divider>

    <v-tabs-window id="settings-tab-window" v-model="activeTab" class="flex-grow-1">
      <template v-if="!loading">
        <v-tabs-window-item v-for="manager in managerList" :key="manager.name" :value="manager.name"
          class="config-tab-window">
          <SettingWindow :key="manager.name" :name="manager.name" />
        </v-tabs-window-item>
      </template>
      <div v-else class="pa-4 text-center">
        <v-progress-circular indeterminate color="primary"></v-progress-circular>
        <p class="mt-2">加载中...</p>
      </div>
    </v-tabs-window>
  </v-card>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import { useStore } from 'vuex';
import { inject } from 'vue';
import PageTitle from '@/components/PageTitle.vue';
import SettingWindow from '@/components/SettingWindow.vue';

// 获取依赖
const snackbar = inject('snackbar');
const store = useStore();

// 本地状态
const managerList = ref([]);
const loading = ref(false);

// 使用计算属性从 store 获取和设置 activeTab
const activeTab = computed({
  get: () => store.state.settingsPageTab,
  set: (value) => store.state.settingsPageTab = value
});

// 获取设置管理器列表
const fetchManagers = async () => {
  loading.value = true;
  try {
    const response = await fetch(`${store.state.apiBaseUrl}/settings`, {
      headers: {
        'Authorization': `Bearer ${store.state.user.jwtToken}`
      }
    });

    const data = await response.json();

    if (data.code !== 0) {
      snackbar.error(`加载设置失败: ${data.msg || '未知错误'}`);
      return;
    }

    managerList.value = data.data.managers || [];

    // 如果没有设置当前标签页或当前标签页不存在，则设置为第一个
    if (!activeTab.value && managerList.value.length > 0) {
      activeTab.value = managerList.value[0].name;
    }
  } catch (error) {
    console.error("获取设置列表出错:", error);
    snackbar.error(`加载设置时出错: ${error.message || '请检查网络连接'}`);
  } finally {
    loading.value = false;
  }
};

// 提供给 PageTitle 的刷新方法
const refreshManagers = () => {
  fetchManagers();
};

// 标签页切换处理函数
const onTabChange = (tab) => {
  console.log(`标签页切换到: ${tab}`);
  // 如果需要，可以在这里添加其他逻辑
};

// 组件挂载时获取数据
onMounted(() => {
  fetchManagers();
});
</script>

<style scoped>
#settings-card {
  margin: 1rem;
  flex: 1;
  min-height: 0;
  /* 解决 flex 布局中 min-height 的问题 */
}

#settings-tabs {
  flex: 0 0 auto;
  /* 防止 tabs 区域被压缩 */
}

.config-tab-window {
  margin-bottom: 20px;
  /* 由内部组件控制内边距 */
}
</style>