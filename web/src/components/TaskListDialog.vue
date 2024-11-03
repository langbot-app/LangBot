<template>
    <v-card class="task-dialog" prepend-icon="mdi-align-horizontal-left" text="用户发起的任务列表" title="任务列表">
        <v-list id="task-list" v-if="taskList.length > 0">
            <TaskCard class="task-card" v-for="task in taskList" :key="task.id" :task="task" />
        </v-list>
        <div v-else><v-alert color="warning" icon="$warning" title="暂无任务" text="暂无已添加的用户任务项" density="compact" style="margin-inline: 1rem;"></v-alert></div>

        <template v-slot:actions>
            <v-btn class="ml-auto" text="关闭" prepend-icon="mdi-close" @click="close"></v-btn>
        </template>
    </v-card>

</template>

<script setup>
defineProps({
})

const emit = defineEmits(['close'])

import TaskCard from '@/components/TaskCard.vue'

import { ref, onMounted, onUnmounted, getCurrentInstance } from 'vue'

const { proxy } = getCurrentInstance()

import { inject } from 'vue'

const snackbar = inject('snackbar')

const close = () => {
    emit('close')
}

const taskList = ref([])

const refresh = () => {
    proxy.$axios.get('/system/tasks', {
        params: {
            type: 'user'
        }
    }).then(response => {
        if (response.data.code != 0) {
            snackbar.error(response.data.message)
            return
        }
        taskList.value = response.data.data.tasks

        // 倒序
        taskList.value.reverse()
    }).catch(error => {
        snackbar.error(error.message)
    })
}

let refreshTask = null
onMounted(() => {
    refresh()
    refreshTask = setInterval(refresh, 1000)
})

onUnmounted(() => {
    clearInterval(refreshTask)
})

</script>

<style scoped>
.task-dialog {
    width: 100%;
}

#task-list {
    max-height: 20rem;
    overflow-y: auto;
    margin-inline: 1rem;
    width: calc(100% - 2.2rem);
    padding-inline: 0.6rem;
}

.task-card {
    /* margin-bottom: 0.1rem; */
    display: flex;
    flex-direction: row;
    /* box-shadow: 1px 1px 1px 1px rgba(0, 0, 0, 0.1); */
    height: 4rem;
    /* border: 0.08rem solid #ccc; */
    box-shadow: 0.1rem 0.1rem 0.2rem 0.05rem #ccc;
    background-color: #ffffff;
}
</style>