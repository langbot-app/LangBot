<template>
    <PageTitle title="仪表盘" @refresh="refresh" />

    <div id="dashboard-content">
        <div id="first-row">
            <v-card id="basic-analysis-number-card">
                <v-card-title class="content-card-title">
                    <v-icon class="content-card-title-icon" icon="mdi-chart-line" />
                    基础数据
                </v-card-title>

                <div id="basic-analysis-number-card-content">
                    <NumberFieldData title="活跃会话" :number="basicData.active_session_count" />
                    <NumberFieldData title="对话总数" :number="basicData.conversation_count" />
                    <NumberFieldData title="请求总数" :number="basicData.query_count" />
                </div>
            </v-card>

            <v-card id="message-platform-card">
                <v-card-title class="content-card-title">
                    <v-icon class="content-card-title-icon" icon="mdi-message-outline" />
                    消息平台
                </v-card-title>

                <div id="message-platform-card-content">
                    <NumberFieldData title="已启用" :number="proxy.$store.state.enabledPlatformCount" link="/settings" linkText="更改配置" />
                </div>
            </v-card>

            <v-card id="plugins-amount-card">
                <v-card-title class="content-card-title">
                    <v-icon class="content-card-title-icon" icon="mdi-puzzle-outline" />
                    插件数量
                </v-card-title>

                <div id="plugins-amount-card-content">
                    <NumberFieldData title="已加载" :number="pluginsAmount" link="/plugins" linkText="管理插件" />
                </div>
            </v-card>
        </div>

        <div id="dashboard-tips">
            * 更多图表将在数据持久化功能更新后可用。
        </div>
    </div>
</template>

<script setup>

import PageTitle from '@/components/PageTitle.vue'
import NumberFieldData from '@/components/NumberFieldData.vue'

import { ref, onMounted, inject, getCurrentInstance } from 'vue'

const { proxy } = getCurrentInstance()

const snackbar = inject('snackbar')

const basicData = ref({
    active_session_count: 0,
    conversation_count: 0,
    query_count: 0,
})

const pluginsAmount = ref(0)

const refresh = () => {
    proxy.$axios.get('/stats/basic').then(res => {
        if (res.data.code != 0) {
            snackbar.error(res.data.msg)
            return
        }
        basicData.value = res.data.data
    }).catch(error => {
        snackbar.error(error)
    })

    proxy.$axios.get('/plugins').then(res => {
        if (res.data.code != 0) {
            snackbar.error(res.data.msg)
            return
        }
        pluginsAmount.value = res.data.data.plugins.length
    }).catch(error => {
        snackbar.error(error)
    })

    proxy.$store.commit('fetchSystemInfo')
}

onMounted(refresh)
</script>

<style scoped>
#dashboard-content {
    display: table;
    width: 100%;
    padding-inline: 1rem;
    margin-top: 1rem;
    overflow-x: auto;
}

#dashboard-tips {
    font-size: 0.8rem;
    color: #222;
    margin-top: 0.7rem;
    margin-left: 0.5rem;
    user-select: none;
}

#first-row {
    display: flex;
    flex-direction: row;
    justify-content: flex-start;
    gap: 1rem;
}

#basic-analysis-number-card {
    width: 35%;
    min-width: 16rem;
    padding-bottom: 0.5rem;
}

#basic-analysis-number-card-content {
    display: flex;
    flex-direction: row;
    justify-content: space-evenly;
}

.content-card-title {
    font-size: 1rem;
    font-weight: 600;
    user-select: none;
}

.content-card-title-icon {
    font-size: 1.2rem;
}

#message-platform-card {
    width: 15%;
    min-width: 6rem;
    padding-bottom: 0.7rem;
}

#plugins-amount-card {
    width: 15%;
    min-width: 6rem;
    padding-bottom: 0.7rem;
}
</style>