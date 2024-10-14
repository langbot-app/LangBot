<template>
    <PageTitle title="日志" @refresh="refresh" />
    <v-card id="toolbar">
        <v-card-text>
            <v-switch class="toolbar-component" color="primary" :model-value="proxy.$store.state.autoRefreshLog"
                @update:model-value="proxy.$store.state.autoRefreshLog = $event" label="自动刷新"></v-switch>
        </v-card-text>
    </v-card>
    <v-card id="log-card">
        <v-card-text id="log-card-text">
            <textarea id="log-textarea" placeholder="点击标题旁的按钮以刷新日志" v-model="logContent" readonly></textarea>
        </v-card-text>
    </v-card>
</template>

<script setup>

import PageTitle from '@/components/PageTitle.vue'
import { ref, getCurrentInstance, onMounted, onUnmounted } from 'vue'

const { proxy } = getCurrentInstance()

const logContent = ref('')

const refresh = () => {
    refreshLog()
}

let logPointer = {
    "start_page_number": 0,
    "start_offset": 0
}

const refreshLog = () => {
    proxy.$axios.get(`/logs`, {
        params: {
            start_page_number: logPointer.start_page_number,
            start_offset: logPointer.start_offset
        }
    }).then(response => {
        logContent.value += response.data.data.logs
        logPointer.start_page_number = response.data.data.end_page_number
        logPointer.start_offset = response.data.data.end_offset
    })
}

let refreshLogTask = null
onMounted(() => {
    refreshLog()

    refreshLogTask = setInterval(() => {
        if (proxy.$store.state.autoRefreshLog) {
            refreshLog()
        }
    }, 1000)
})

onUnmounted(() => {
    clearInterval(refreshLogTask)
})
</script>

<style scoped>
#toolbar {
    display: flex;
    justify-content: center;
    align-items: center;
    margin: 1rem;
    margin-top: 1rem;
    height: 3rem;
    border-radius: 0.3rem;
}

.toolbar-component {
    margin-top: 1.4rem;
}


#log-card {
    margin: 1rem;
    margin-top: 1rem;
    height: calc(100vh - 9.5rem);
    border-radius: 0.3rem;
}


#log-textarea {
    /* height: 100%; */
    height: 100%;
    width: 100%;
    resize: none;
    border: none;
    outline: none;
    appearance: none;
    /* background-color: #eee; */
}

#log-card-text {
    display: flex;
    height: 100%;
}
</style>