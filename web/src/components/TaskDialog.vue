<template>
    <v-card prepend-icon="mdi-align-horizontal-left" text="用户发起的任务列表" title="任务列表">
        <v-list id="plugin-orchestration-list">
            <draggable v-model="plugins" item-key="name" group="plugins" @start="drag = true"
                id="plugin-orchestration-draggable"
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
            <v-btn class="ml-auto" text="关闭" prepend-icon="mdi-close" @click="close"></v-btn>
        </template>
    </v-card>
</template>

<script setup>
defineProps({
})

const emit = defineEmits(['close'])

import { ref } from 'vue'

import { inject } from 'vue'

const snackbar = inject('snackbar')

const close = () => {
    emit('close')
}
</script>

<style scoped>

</style>
