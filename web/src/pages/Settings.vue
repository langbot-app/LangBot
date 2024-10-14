<template>
  <PageTitle title="设置" @refresh="refresh" />

  <v-card id="settings-card">
    <v-tabs id="settings-tabs" v-model="tab" show-arrows center-active>
      <v-tab v-for="manager in managerList" :key="manager.name" :value="manager.name">{{ manager.name }}</v-tab>
    </v-tabs>

    <v-tabs-window id="settings-tab-window" v-model="tab">
      <v-tabs-window-item v-for="manager in managerList" :key="manager.name" :value="manager.name"
        class="config-tab-window">
        <v-card class="config-tab-toolbar">
          <v-tooltip :text="manager.schema == null ? '仅配置文件管理器提供了 JSON Schema 时支持可视化配置' : '切换编辑模式'" location="top">
            <template v-slot:activator="{ props }">

              <v-btn-toggle id="config-type-toggle" color="primary" v-model="configType" mandatory v-bind="props">

                <v-btn class="config-type-toggle-btn" value="ui" :readonly="manager.schema == null">
                  <v-icon>mdi-view-dashboard-edit-outline</v-icon>
                </v-btn>
                <v-btn class="config-type-toggle-btn" value="json" :readonly="manager.schema == null">
                  <v-icon>mdi-code-json</v-icon>
                </v-btn>
              </v-btn-toggle>
            </template>
          </v-tooltip>
        </v-card>
      </v-tabs-window-item>
    </v-tabs-window>
  </v-card>

</template>

<script setup>

import PageTitle from '@/components/PageTitle.vue'
import { ref, getCurrentInstance, onMounted, onUnmounted } from 'vue'

const { proxy } = getCurrentInstance()

const managerList = ref([])
const tab = ref('')
const configType = ref('json')  // ui or json

const refresh = () => {
  proxy.$axios.get('/settings').then(response => {
    managerList.value = response.data.data.managers
  })
}

onMounted(async () => {
  refresh()
})

</script>

<style scoped>
#settings-card {
  margin: 1rem;
  height: calc(100% - 5rem);
  /* max-height: calc(100% - 5rem); */
  display: flex;
  flex-direction: column;
  overflow: hidden;
  /* background-color: #f0f0f0; */
}

#settings-tabs {
  height: 3rem;
  overflow: hidden;
}

#settings-tab-window {
  height: calc(100vh - 9rem);
  overflow: hidden;
  /* background-color: aqua; */
}

.config-tab-window {
  overflow: auto;
}

.config-tab-toolbar {
  margin: 0.5rem;
  height: 4rem;
  display: flex;
  flex-direction: row;
  justify-content: flex-start;
  align-items: center;
}

#config-type-toggle {
  margin: 0.5rem;
  box-shadow: 0 0 0 2px #dddddd;
}

.config-type-toggle-btn {}

.config-tab-content {
  margin: 0.2rem;
}
</style>