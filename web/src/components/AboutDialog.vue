<template>
    <v-card class="about-dialog">

        <div class="d-flex flex-column align-center pa-4">
            <v-img class="about-logo" src="@/assets/langbot-logo.png" width="64" alt="LangBot Logo" />

            <div class="text-center">
                <div class="about-title mt-2">
                    LangBot
                </div>

                <div class="about-subtitle mt-1">
                    版本 {{ appVersion }}
                </div>

                <div class="about-copyright mt-1 mb-2">
                    版权所有 © 2024 RockChinQ
                </div>
            </div>
        </div>

        <template v-slot:actions>
            <v-btn class="about-action-btn" text="代码仓库" prepend-icon="mdi-github"
                href="https://github.com/RockChinQ/LangBot" target="_blank" rel="noopener noreferrer"></v-btn>
            <v-spacer></v-spacer>
            <v-btn class="about-action-btn" text="关闭" prepend-icon="mdi-close" @click="close"></v-btn>
        </template>
    </v-card>
</template>

<script setup>
import { computed, getCurrentInstance } from 'vue'

const { proxy } = getCurrentInstance()

// 使用 computed 属性来获取版本号
const appVersion = computed(() => {
    try {
        return proxy?.$store?.state?.version ?? '未知';
    } catch (error) {
        if (process.env.NODE_ENV === 'development') {
            console.error('获取 Store 版本号失败:', error);
        }
        return '未知';
    }
})

const emit = defineEmits(['close'])

const close = () => {
    emit('close')
}
</script>

<style scoped>
.about-dialog {
    padding-top: 2rem;
}

.about-title {
    font-size: 1.2rem;
    font-weight: 500;
}

.about-subtitle,
.about-copyright {
    font-size: 0.8rem;
    color: rgba(0, 0, 0, 0.6);
}

.about-action-btn {
    text-transform: none;
}
</style>