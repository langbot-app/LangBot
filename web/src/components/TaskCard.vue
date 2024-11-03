<template>
    <div class="task-card">
        <div class="task-card-icon">
            <v-progress-circular :size="25" :width="2" indeterminate v-if="task.runtime.state == 'PENDING'" />
            <v-icon v-else-if="task.runtime.state == 'FINISHED' && task.runtime.exception == null"
                style="color: #4caf50;" :size="25" icon="mdi-check" />
            <v-icon v-else-if="task.runtime.state == 'CANCELLED'" style="color: #f44336;" :size="25" icon="mdi-close" />

            <v-icon v-else-if="task.runtime.state == 'FINISHED' && task.runtime.exception != null" style="color: #f44336;"
                :size="25" icon="mdi-alert-circle-outline" v-bind="activatorProps" />
        </div>

        <div class="task-card-content">
            <div class="task-card-kind">{{ task.kind }}</div>
            <div class="task-card-label">{{ task.label }}</div>
            <v-chip class="task-card-action" color="primary" variant="outlined" size="small" density="compact"
                v-if="task.runtime.state == 'PENDING'">正在执行: {{ task.task_context.current_action }}</v-chip>
            <v-chip class="task-card-action" color="success" variant="outlined" size="small" density="compact"
                v-else-if="task.runtime.state == 'FINISHED' && task.runtime.exception == null">完成</v-chip>

            <v-dialog max-width="500" persistent v-model="exceptionDialogShow">
                <template v-slot:activator="{ props: activatorProps }">
                    <v-chip class="task-card-action" color="error" variant="outlined" size="small" density="compact"
                        v-if="task.runtime.state == 'FINISHED' && task.runtime.exception != null"
                        v-bind="activatorProps">{{ task.runtime.exception }}</v-chip>
                </template>

                <v-card prepend-icon="mdi-alert-circle-outline"
                    :text="task.runtime.exception_traceback"
                    title="任务执行失败">
                    <template v-slot:actions>
                        <v-spacer></v-spacer>

                        <v-btn @click="exceptionDialogShow = false" prepend-icon="mdi-close">
                            关闭
                        </v-btn>
                    </template>
                </v-card>
            </v-dialog>
        </div>

        <div class="task-card-actions">
            <!-- <v-icon icon="mdi-details" /> -->
            <v-dialog max-width="500" persistent v-model="detailsDialogShow">
                <template v-slot:activator="{ props: activatorProps }">
                    <v-btn icon="mdi-file-outline" variant="text" v-bind="activatorProps" />
                </template>

                <v-card prepend-icon="mdi-file-outline" id="task-details-card"
                    :title="'任务执行日志 - '+task.label">

                    <div id="task-details-log-container">
                            <textarea id="task-details-log" v-model="task.task_context.log" readonly />

                        <v-spacer></v-spacer>
                    </div>
                    <template v-slot:actions>

                        <v-btn @click="detailsDialogShow = false" prepend-icon="mdi-close">
                            关闭
                        </v-btn>
                    </template>
                </v-card>
            </v-dialog>
        </div>
    </div>
</template>

<script setup>
defineProps({
    task: {
        type: Object,
        required: true
    }
})

import { ref } from 'vue'

const exceptionDialogShow = ref(false)
const detailsDialogShow = ref(false)
</script>

<style scoped>
.task-card {
    display: flex;
    flex-direction: row;
    align-items: center;
    justify-content: flex-start;
    width: 100%;
    padding-inline: 0.5rem;
}

.task-card-icon {
    margin-right: 1rem;
    margin-left: 0.8rem;
}

.task-card-content {
    flex: 1;
    margin-left: 0.4rem;
    display: flex;
    flex-direction: column;
    gap: 0.02rem;
    user-select: none;
}

.task-card-kind {
    font-size: 0.6rem;
    color: #666;
}

.task-card-label {
    font-size: 0.8rem;
    color: #333;
}

.task-card-action {
    font-size: 0.6rem;
    width: fit-content;
    padding-inline: 0.3rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.task-card-actions {
    justify-self: flex-end;
}


#task-details-log {
    width: calc(100% - 2rem);
    height: 10rem;
    resize: none;
    border: none;
    padding: 0.6rem;
    font-size: 0.8rem;
    outline: none;
    overflow: auto;
    appearance: none;
    background-color: #f6f6f6;
    margin-inline: 1rem;
}
</style>
