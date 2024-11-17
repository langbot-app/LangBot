<template>
  <PageTitle title="设置" @refresh="refresh" />

  <v-card id="settings-card">
    <v-tabs id="settings-tabs" v-model="proxy.$store.state.settingsPageTab" show-arrows center-active
      @update:model-value="onTabChange">
      <v-tooltip v-for="manager in managerList" :key="manager.name" :text="manager.description"
        location="top">
        <template v-slot:activator="{ props }">
          <v-tab v-bind="props" :value="manager.name" style="text-transform: none;">{{ manager.name }}</v-tab>
        </template>
      </v-tooltip>
    </v-tabs>
    <v-tabs-window id="settings-tab-window" v-model="proxy.$store.state.settingsPageTab">
      <v-tabs-window-item v-for="manager in managerList" :key="manager.name" :value="manager.name"
        class="config-tab-window">
        <SettingWindow style="height: 100%;width: 100%;" :name="manager.name" />
         <!-- {{ manager.name }} -->
      </v-tabs-window-item>
    </v-tabs-window>
  </v-card>

</template>

<script setup>

import PageTitle from '@/components/PageTitle.vue'
import SettingWindow from '@/components/SettingWindow.vue'
import { ref, getCurrentInstance, onMounted } from 'vue'

import {inject} from "vue";

const snackbar = inject('snackbar');

const { proxy } = getCurrentInstance()

const managerList = ref([])

const refresh = () => {
  proxy.$axios.get('/settings').then(response => {

    if (response.data.code != 0) {
      snackbar.error(response.data.msg)
      return
    }

    managerList.value = response.data.data.managers

    if (proxy.$store.state.settingsPageTab == '') {
      proxy.$store.state.settingsPageTab = managerList.value[0].name
    }
  }).catch(error => {
    snackbar.error(error)
  })
}

const onTabChange = (tab) => {
  console.log(tab)
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

</style>