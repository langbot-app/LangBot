<template>
    <PageTitle title="插件" @refresh="refresh" />
    <v-card id="plugins-toolbar">
        <div id="view-btns">
            <v-btn-toggle id="plugins-view-toggle" color="primary" v-model="proxy.$store.state.pluginsView" mandatory density="compact">
                <v-btn class="plugins-view-toggle-btn" value="installed" density="compact">已安装</v-btn>
                <v-btn class="plugins-view-toggle-btn" value="market" density="compact">插件市场</v-btn>
            </v-btn-toggle>
        </div>
        <div id="operation-btns">
            <v-tooltip text="设置插件优先级" location="top">
                <template v-slot:activator="{ props }">
                    <v-btn prepend-icon="mdi-priority-high" v-bind="props" :disabled="plugins.length == 0">
                        编排

                        <v-dialog activator="parent" max-width="500" persistent v-model="isOrchestrationDialogActive">
                            <template v-slot:default="{ isActive }">
                                <v-card prepend-icon="mdi-priority-high" text="优先级影响插件的加载、事件触发顺序" title="设置插件优先级">
                                    <v-list id="plugin-orchestration-list">
                                        <draggable v-model="plugins" item-key="name" group="plugins"
                                            @start="drag = true" id="plugin-orchestration-draggable"
                                            @end="drag = false">
                                            <template #item="{ element }">
                                                <div class="plugin-orchestration-item">
                                                    <div class="plugin-orchestration-item-title">
                                                        <div class="plugin-orchestration-item-author">
                                                            {{ element.author }} /
                                                        </div>
                                                        <div class="plugin-orchestration-item-name">
                                                            {{ element.name }}
                                                        </div>
                                                    </div>

                                                    <div class="plugin-orchestration-item-action">
                                                        <v-icon>mdi-drag</v-icon>
                                                    </div>
                                                </div>
                                            </template>
                                        </draggable>
                                    </v-list>

                                    <template v-slot:actions>
                                        <v-btn class="ml-auto" text="关闭" prepend-icon="mdi-close"
                                            @click="cancelOrderChanges"></v-btn>
                                        <v-btn color="primary" prepend-icon="mdi-content-save-outline"
                                            @click="saveOrder">应用</v-btn>
                                    </template>
                                </v-card>
                            </template>
                        </v-dialog>
                    </v-btn>
                </template>
            </v-tooltip>

            <v-btn color="primary" prepend-icon="mdi-plus">
                安装

                <v-dialog activator="parent" max-width="500" persistent v-model="isInstallDialogActive">
                    <template v-slot:default="{ isActive }">

                        <v-card title="从 GitHub 安装插件" prepend-icon="mdi-github">

                            <div id="plugin-install-dialog-content">
                                <div>
                                    目前仅支持从 GitHub 安装，插件列表：<a
                                        href="https://github.com/stars/RockChinQ/lists/qchatgpt-%E6%8F%92%E4%BB%B6"
                                        target="_blank">LangBot 插件</a>
                                </div>
                                <v-text-field v-model="installDialogSource" label="插件源码地址" />
                            </div>

                            <template v-slot:actions>
                                <v-btn class="ml-auto" text="取消" prepend-icon="mdi-close"
                                    @click="isInstallDialogActive = false"></v-btn>
                                <v-btn color="primary" prepend-icon="mdi-content-save-outline"
                                    @click="installPlugin">安装</v-btn>
                            </template>

                        </v-card>
                    </template>
                </v-dialog>
            </v-btn>
        </div>
    </v-card>
    <div class="plugins-container" v-if="proxy.$store.state.pluginsView == 'installed'">
        <v-alert id="no-plugins-alert" v-if="plugins.length == 0" color="warning" icon="$warning" title="暂无插件" text="暂无已安装的插件，请安装插件" density="compact" style="margin-inline: 1rem;"></v-alert>
        <PluginCard class="plugin-card" v-if="plugins.length > 0" v-for="plugin in plugins" :key="plugin.name" :plugin="plugin"
            @toggle="togglePlugin" @update="updatePlugin" @remove="removePlugin" />
    </div>
    <div class="plugins-container" v-if="proxy.$store.state.pluginsView == 'market'">
        <Marketplace @installPlugin="installMarketplacePlugin" />
    </div>
</template>

<script setup>

import PageTitle from '@/components/PageTitle.vue'
import PluginCard from '@/components/PluginCard.vue'
import Marketplace from '@/components/Marketplace.vue'

import draggable from 'vuedraggable'

import { ref, getCurrentInstance, onMounted } from 'vue'

import { inject } from "vue";

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
    proxy.$axios.put(`/plugins/${plugin.author}/${plugin.name}/toggle`, {
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

const updatePlugin = (plugin) => {
    proxy.$axios.post(`/plugins/${plugin.author}/${plugin.name}/update`).then(res => {
        if (res.data.code != 0) {
            snackbar.error(res.data.msg)
            return
        }
        snackbar.success(`已添加更新任务 请到任务列表查看进度`)
    }).catch(error => {
        snackbar.error(error)
    })
}

const removePlugin = (plugin) => {
    proxy.$axios.delete(`/plugins/${plugin.author}/${plugin.name}`).then(res => {
        if (res.data.code != 0) {
            snackbar.error(res.data.msg)
            return
        }
        snackbar.success(`已添加删除任务 请到任务列表查看进度`)
    }).catch(error => {
        snackbar.error(error)
    })
}

const installMarketplacePlugin = (repository) => {

    installDialogSource.value = 'https://'+repository
    isInstallDialogActive.value = true
}

const installPlugin = () => {

    if (installDialogSource.value == '' || installDialogSource.value.trim() == '') {
        snackbar.error("请输入插件仓库地址")
        return
    }

    proxy.$axios.post(`/plugins/install/github`, {
        source: installDialogSource.value
    }).then(res => {
        if (res.data.code != 0) {
            snackbar.error(res.data.msg)
            return
        }
        installDialogSource.value = ''
        snackbar.success(`已添加插件安装任务 请到任务列表查看进度`)
        isInstallDialogActive.value = false
    }).catch(error => {
        snackbar.error(error)
    })
}

const isOrchestrationDialogActive = ref(false)

const cancelOrderChanges = () => {
    refresh()
    isOrchestrationDialogActive.value = false
}

const saveOrder = () => {
    // 为所有插件的 priority 赋值，倒序
    plugins.value.forEach(plugin => {
        plugin.priority = plugins.value.length - plugins.value.indexOf(plugin)
    })

    proxy.$axios.put('/plugins/reorder', {
        plugins: plugins.value
    }).then(res => {
        refresh()
        snackbar.success('插件优先级已保存')
        isOrchestrationDialogActive.value = false
    }).catch(error => {
        snackbar.error(error)
    })
}

const isInstallDialogActive = ref(false)
const installDialogSource = ref('')

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

#plugins-view-toggle {
    margin: 0.5rem;
    box-shadow: 0 0 0 2px #dddddd;
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
    justify-content: flex-start;
    flex-wrap: wrap;
    gap: 16px;
    margin-inline: 1rem;
}

#no-plugins-alert {
    margin: 1rem;
}

.plugin-card {
    width: 18rem;
    height: 8rem;
}

#plugin-orchestration-list {
    max-height: 20rem;
    overflow-y: auto;
    margin-inline: 1rem;
    width: calc(100% - 2rem);
    /* background-color: aqua; */
}

#plugin-orchestration-draggable {
    display: flex;
    flex-direction: column;
    align-items: center;
}

.plugin-orchestration-item {
    cursor: move;
    width: calc(100% - 2rem);
    box-shadow: 0.1rem 0.1rem 0.2rem 0.05rem #ccc;
    background-color: #ffffff;
    display: flex;
    flex-direction: row;
    padding: 0.5rem;
    justify-content: space-between;
}

.plugin-orchestration-item-title {
    display: flex;
    flex-direction: column;
}

.plugin-orchestration-item-author {
    color: #666;
    font-size: 0.7rem;
}

.plugin-orchestration-item-name {
    font-size: 1.1rem;
    font-weight: 500;
}

.plugin-orchestration-item-action {
    display: flex;
    flex-direction: row;
    align-items: center;
}

#plugin-install-dialog-content {
    width: calc(100% - 3rem);
    margin-inline: 1.5rem;
    display: flex;
    flex-direction: column;
    gap: 1rem;
}
</style>
