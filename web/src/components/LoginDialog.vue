<template>
    <v-container class="login-page-container fill-height" fluid>
        <v-row justify="center" align="center">
            <v-col cols="12" sm="8" md="6" lg="4" xl="3">
                <v-card id="login-card" elevation="5">
                    <v-card-title class="d-flex align-center" style="gap: 0.5rem;">
                        <img src="@/assets/langbot-logo.png" height="32" width="32" />
                        <span>登录 LangBot</span>
                    </v-card-title>

                    <v-form ref="loginForm" v-model="isFormValid" @submit.prevent="handleLogin">
                        <v-card-text class="d-flex flex-column" style="gap: 0.5rem;margin-top: 1rem;">
                            <v-text-field v-model="user" variant="outlined" label="邮箱"
                                :rules="[rules.required, rules.email]" clearable :disabled="isLoading" />
                            <v-text-field v-model="password" variant="outlined" label="密码" :rules="[rules.required]"
                                type="password" clearable :disabled="isLoading" @keyup.enter="handleLogin" />
                        </v-card-text>

                        <v-card-actions>
                            <v-btn color="secondary" variant="flat" @click="goToRegister" :disabled="isLoading">
                                注册
                            </v-btn>
                            <v-spacer></v-spacer>
                            <v-btn color="primary" variant="flat" @click="handleLogin" :loading="isLoading"
                                :disabled="isLoading">
                                登录
                            </v-btn>
                        </v-card-actions>
                    </v-form>
                </v-card>
            </v-col>
        </v-row>
    </v-container>
</template>

<script setup>
import { ref, computed, getCurrentInstance, inject, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useStore } from 'vuex'

const router = useRouter()
const store = useStore()
const { proxy } = getCurrentInstance()
const snackbar = inject('snackbar')

// 响应式状态
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

// 组件加载时检查系统是否初始化
onMounted(async () => {
    try {
        // 修复API请求路径，移除重复的api/v1前缀
        const response = await proxy.$axios.get('/user/init')
        if (response.data.code === 0) {
            const initialized = response.data.data.initialized
            localStorage.setItem('system-initialized', initialized)

            if (!initialized) {
                router.push('/init')
            }
        }
    } catch (error) {
        console.error('检查系统初始化状态失败', error)
    }
})

// 跳转到注册页面
const goToRegister = () => {
    router.push('/init')
}

// 登录处理函数
const handleLogin = async () => {
    // 表单验证
    const { valid } = await loginForm.value?.validate() || { valid: isFormValid.value }
    if (!valid) return

    try {
        isLoading.value = true
        // 修复API请求路径，移除重复的api/v1前缀
        const response = await proxy.$axios.post('/user/auth', {
            user: user.value,
            password: password.value
        })

        if (response.data.code === 0) {
            // 登录成功处理
            const token = response.data.data.token

            // 存储令牌并设置全局请求头
            localStorage.setItem('user-token', token)
            proxy.$axios.defaults.headers.common['Authorization'] = `Bearer ${token}`

            // 更新状态并验证令牌
            store.commit('setUserToken', token)
            snackbar.success('登录成功')

            // 检查token有效性
            await checkTokenValidity()

            // 登录成功后导航到主页
            router.push('/')
        } else {
            snackbar.error(response.data.msg || '登录失败')
        }
    } catch (err) {
        console.error('登录错误:', err)
        const errorMessage = err.response?.data?.msg || '登录失败'
        snackbar.error(errorMessage)
    } finally {
        isLoading.value = false
    }
}

// 检查token有效性
const checkTokenValidity = async () => {
    try {
        // 修复API请求路径，移除重复的api/v1前缀
        const response = await proxy.$axios.get('/user/check-token')
        if (response.data.code === 0) {
            store.commit('setTokenValid', true)
        } else {
            store.commit('setTokenValid', false)
        }
    } catch (err) {
        store.commit('setTokenValid', false)
    } finally {
        store.commit('setTokenChecked', true)
    }
}
</script>

<style scoped>
.login-page-container {
    background-color: #f6f6f6;
    display: flex;
    justify-content: center;
    align-items: center;
    min-height: 100vh;
    /* 确保容器至少有视口高度 */
}

#login-card {
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