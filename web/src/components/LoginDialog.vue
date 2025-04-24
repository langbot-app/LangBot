<template>
    <v-dialog v-model="dialog" width="350" persistent>
        <v-card id="login-dialog">
            <v-card-title class="d-flex align-center" style="gap: 0.5rem;">
                <img src="@/assets/langbot-logo.png" height="32" width="32" />
                <span>登录 LangBot</span>
            </v-card-title>

            <v-form ref="loginForm" v-model="isFormValid" @submit.prevent="handleLogin">
                <v-card-text class="d-flex flex-column" style="gap: 0.5rem;margin-bottom: -2rem;margin-top: 1rem;">
                    <v-text-field v-model="user" variant="outlined" label="邮箱" :rules="[rules.required, rules.email]"
                        clearable :disabled="isLoading" />
                    <v-text-field v-model="password" variant="outlined" label="密码" :rules="[rules.required]"
                        type="password" clearable :disabled="isLoading" @keyup.enter="handleLogin" />
                </v-card-text>

                <v-card-actions>
                    <v-spacer></v-spacer>
                    <v-btn color="primary" variant="flat" @click="handleLogin" :loading="isLoading"
                        :disabled="isLoading">
                        登录
                    </v-btn>
                </v-card-actions>
            </v-form>
        </v-card>
    </v-dialog>
</template>

<script setup>
import { ref, computed, getCurrentInstance, inject } from 'vue'
import { useRouter } from 'vue-router'
import { useStore } from 'vuex'

const router = useRouter()
const store = useStore()
const { proxy } = getCurrentInstance()

const emit = defineEmits(['error', 'success', 'checkToken'])

// 响应式状态
const dialog = ref(true)
const user = ref('')
const password = ref('')
const isLoading = ref(false)
const isFormValid = ref(false)
const loginForm = ref(null)

// 表单验证规则
const rules = {
    required: value => !!value || '必填项',
    email: value => {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
        return emailRegex.test(value) || '请输入有效的邮箱地址'
    }
}

// 登录处理函数
const handleLogin = async () => {
    // 表单验证
    const isValid = loginForm.value?.validate()
    if (!isValid) return

    try {
        isLoading.value = true
        const response = await proxy.$axios.post('/user/auth', {
            user: user.value,
            password: password.value
        })

        if (response.data.code == 0) {
            // 登录成功处理
            const token = response.data.data.token

            // 存储令牌并设置全局请求头
            localStorage.setItem('user-token', token)
            proxy.$axios.defaults.headers.common['Authorization'] = `Bearer ${token}`

            // 更新状态并验证令牌
            await store.commit('setUserToken', token)
            emit('success', '登录成功')
            emit('checkToken')

            // 延迟导航到主页
            setTimeout(() => {
                router.push('/')
            }, 1000)
        } else {
            emit('error', response.data.msg)
        }
    } catch (err) {
        const errorMessage = err.response?.data?.msg || '登录失败'
        emit('error', errorMessage)
    } finally {
        isLoading.value = false
    }
}
</script>

<style scoped>
#login-dialog {
    padding-top: 0.8rem;
    padding-bottom: 0.5rem;
    padding-inline: 0.5rem;
}
</style>