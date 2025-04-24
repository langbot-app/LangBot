<template>
    <v-container class="init-page-container fill-height" fluid>
        <v-row justify="center" align="center">
            <v-col cols="12" sm="8" md="6" lg="4" xl="3">
                <v-card id="init-card" elevation="5">
                    <v-card-title class="d-flex align-center" style="gap: 0.5rem;">
                        <img src="@/assets/langbot-logo.png" height="32" width="32" />
                        <span>系统初始化</span>
                    </v-card-title>

                    <v-form ref="initForm" v-model="isFormValid" @submit.prevent="initialize">
                        <v-card-text>
                            <p>请输入初始管理员邮箱和密码。</p>
                        </v-card-text>

                        <v-card-text class="d-flex flex-column" style="gap: 0.5rem;">
                            <v-text-field v-model="user" variant="outlined" label="管理员邮箱"
                                :rules="[rules.required, rules.email]" clearable :disabled="isLoading" />
                            <v-text-field v-model="password" variant="outlined" label="管理员密码" :rules="[rules.required]"
                                type="password" clearable :disabled="isLoading" @keyup.enter="initialize" />
                        </v-card-text>

                        <v-card-actions>
                            <v-spacer></v-spacer>
                            <v-btn color="primary" variant="flat" @click="initialize" :loading="isLoading"
                                :disabled="isLoading" prepend-icon="mdi-check">
                                初始化
                            </v-btn>
                        </v-card-actions>
                    </v-form>
                </v-card>
            </v-col>
        </v-row>
    </v-container>
</template>

<script setup>
import { ref, inject, getCurrentInstance } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const { proxy } = getCurrentInstance()

const emit = defineEmits(['error', 'success', 'checkSystemInitialized'])

const user = ref('')
const password = ref('')
const isFormValid = ref(false)
const isLoading = ref(false)
const initForm = ref(null)

const snackbar = inject('snackbar')

const rules = {
    required: value => !!value || '必填项',
    email: value => {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
        return emailRegex.test(value) || '请输入有效的邮箱地址'
    }
}

const initialize = async () => {
    // 表单验证
    const { valid } = await initForm.value?.validate() || { valid: isFormValid.value }
    if (!valid) return

    isLoading.value = true

    try {
        // 修复API请求路径，移除重复的api/v1前缀
        const res = await proxy.$axios.post('/user/init', {
            user: user.value,
            password: password.value
        })

        emit('success', '系统初始化成功')
        emit('checkSystemInitialized')

        if (snackbar) {
            snackbar.success('系统初始化成功')
        }

        // 存储系统已初始化的状态
        localStorage.setItem('system-initialized', 'true')

        // 初始化成功后跳转到登录界面
        setTimeout(() => {
            router.push('/login')
        }, 1000) // 延迟1秒跳转，让用户看到成功提示

    } catch (err) {
        console.error('初始化错误:', err)
        const errorMessage = err.response?.data?.msg || '系统初始化失败'
        emit('error', errorMessage)

        if (snackbar) {
            snackbar.error(errorMessage)
        }
    } finally {
        isLoading.value = false
    }
}
</script>

<style scoped>
.init-page-container {
    background-color: #f6f6f6;
    display: flex;
    justify-content: center;
    align-items: center;
    min-height: 100vh;
    /* 确保容器至少有视口高度 */
}

#init-card {
    padding-top: 0.8rem;
    padding-bottom: 0.5rem;
    padding-inline: 1rem;
    border-radius: 8px;
    max-width: 450px;
    width: 100%;
    margin: auto;
    /* 添加自动边距确保卡片居中 */
}
</style>
