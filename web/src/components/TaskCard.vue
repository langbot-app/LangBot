<template>
    <div class="task-card">
        <div class="task-card-icon">
            <v-progress-circular :size="25" :width="2" indeterminate v-if="task.runtime.state == 'PENDING'" />
            <v-icon v-else-if="task.runtime.state == 'FINISHED'" style="color: #4caf50;" :size="25" icon="mdi-check" />
            <v-icon v-else-if="task.runtime.state == 'CANCELLED'" style="color: #f44336;" :size="25" icon="mdi-close" />
        </div>

        <div class="task-card-content">
            <div class="task-card-kind">{{ task.kind }}</div>
            <div class="task-card-label">{{ task.label }}</div>
            <v-chip class="task-card-action" color="primary" variant="outlined" size="small" density="compact">正在执行: {{ task.task_context.current_action }}</v-chip>
        </div>

        <div class="task-card-actions">
            <!-- <v-icon icon="mdi-details" /> -->
             <v-btn icon="mdi-information-outline" variant="text" />
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

</style>