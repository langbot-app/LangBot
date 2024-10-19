<template>
    <PageTitle title="插件" @refresh="refresh" />
    <v-card id="plugins-toolbar">
        <div id="view-btns">
        </div>
        <div id="operation-btns">
            <v-tooltip text="设置插件优先级" location="top">
                <template v-slot:activator="{ props }">
                    <v-btn prepend-icon="mdi-priority-high" v-bind="props">
                        编排
                    </v-btn>
                </template>
            </v-tooltip>
            <v-btn color="primary" prepend-icon="mdi-plus">
                安装
            </v-btn>
        </div>
    </v-card>
    <div class="plugins-container">
        <PluginCard class="plugin-card" v-for="plugin in plugins" :key="plugin.name" :plugin="plugin" @toggle="togglePlugin" />
    </div>
</template>

<script setup>

import PageTitle from '@/components/PageTitle.vue'
import PluginCard from '@/components/PluginCard.vue'

import { ref, getCurrentInstance, onMounted } from 'vue'

import {inject} from "vue";

const snackbar = inject('snackbar');

const { proxy } = getCurrentInstance()

const plugins = ref([])

const refresh = () => {
    proxy.$axios.get('/plugins').then(res => {
        if (res.data.code != 0) {
            snackbar.error(res.data.msg)
            return
        }
        plugins.value = res.data.data.plugins
    }).catch(error => {
        snackbar.error(error)
    })
}

onMounted(refresh)

const togglePlugin = (plugin) => {
    proxy.$axios.put(`/plugins/toggle/${plugin.author}/${plugin.name}`, {
        target_enabled: !plugin.enabled
    }).then(res => {
        if (res.data.code != 0) {
            snackbar.error(res.data.msg)
            return
        }
        refresh()
    }).catch(error => {
        snackbar.error(error)
    })
}


</script>

<style scoped>

#plugins-toolbar {
  margin-top: 1rem;
  margin-inline: 1rem;
  height: 3.2rem;
  display: flex;
  flex-direction: row;
  justify-content: space-between;
  align-items: center;
}

#view-btns {
    display: flex;
    flex-direction: row;
    align-items: center;
    gap: 1rem;
    margin-left: 1rem;
}

#operation-btns {
    display: flex;
    flex-direction: row;
    align-items: center;
    gap: 1rem;
    margin-right: 1rem;
}

.plugins-container {
    display: flex;
    flex-direction: row;
    flex-wrap: wrap;
    gap: 16px;
    margin-inline: 1rem;
}

.plugin-card {
    width: 18rem;
    height: 8rem;
}

</style>
