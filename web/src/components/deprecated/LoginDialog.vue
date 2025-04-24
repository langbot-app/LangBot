<template>
    <div class="login-container">
        <div class="login-card">
            <div class="login-icon">
                <img src="@/assets/langbot-logo.png" alt="LangBot Logo" />
            </div>
            <div class="sign-in-label">通过 LangBot 账户登录</div>

            <form ref="loginForm" @submit.prevent="handleLogin" class="login-form">
                <div class="input-group">
                    <input id="email" v-model="user" type="email" placeholder="电子邮件" :disabled="isLoading"
                        @blur="validateEmail" required class="custom-input" />
                    <div class="error-message" v-if="emailError">{{ emailError }}</div>
                </div>

                <div class="input-group">
                    <input id="password" v-model="password" type="password" placeholder="密码" :disabled="isLoading"
                        @keyup.enter="handleLogin" required class="custom-input" />
                    <div class="error-message" v-if="passwordError">{{ passwordError }}</div>
                </div>

                <button type="submit" class="login-button" :disabled="isLoading || !isFormValid"
                    :class="{ 'button-loading': isLoading }">
                    <span v-if="isLoading" class="loading-spinner"></span>
                    <span>继续</span>
                </button>
            </form>

            <div class="divider">
                <span class="divider-line"></span>
                <span class="divider-text">或</span>
                <span class="divider-line"></span>
            </div>

            <button type="button" class="create-account-button" @click="goToRegister" :disabled="isLoading">
                创建 LangBot 账户
            </button>
        </div>
    </div>
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
const emailError = ref('')
const passwordError = ref('')
const loginForm = ref(null)

// 表单验证
const validateEmail = () => {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    if (!user.value) {
        emailError.value = '邮箱不能为空'
        return false
    } else if (!emailRegex.test(user.value)) {
        emailError.value = '请输入有效的邮箱地址'
        return false
    } else {
        emailError.value = ''
        return true
    }
}

const validatePassword = () => {
    if (!password.value) {
        passwordError.value = '密码不能为空'
        return false
    } else {
        passwordError.value = ''
        return true
    }
}

const isFormValid = computed(() => {
    return !emailError.value && !passwordError.value && user.value && password.value
})

// 组件加载时检查系统是否初始化
onMounted(async () => {
    try {
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
    const isEmailValid = validateEmail()
    const isPasswordValid = validatePassword()

    if (!isEmailValid || !isPasswordValid) return

    try {
        isLoading.value = true
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
.login-container {
    display: flex;
    justify-content: center;
    align-items: center;
    min-height: 100vh;
    background-color: #f6f6f6;
    color: #333;
    font-family: SF Pro Text, Helvetica Neue, sans-serif;
    -webkit-font-smoothing: antialiased;
}

.login-card {
    width: 100%;
    max-width: 500px;
    background-color: #ffffff;
    border-radius: 12px;
    padding: 40px 30px;
    display: flex;
    flex-direction: column;
    align-items: center;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
    border: 1px solid rgba(0, 0, 0, 0.05);
}

.login-icon {
    width: 70px;
    height: 70px;
    margin-bottom: 20px;
    display: flex;
    justify-content: center;
    align-items: center;
}

.login-icon img {
    max-width: 100%;
    max-height: 100%;
}

.sign-in-label {
    font-size: 18px;
    font-weight: 500;
    margin-bottom: 30px;
    color: #333;
}

.login-form {
    width: 100%;
    display: flex;
    flex-direction: column;
    gap: 16px;
}

.input-group {
    width: 100%;
    position: relative;
}

.custom-input {
    width: 100%;
    height: 44px;
    background-color: #f5f5f5;
    border: 1px solid #e0e0e0;
    border-radius: 10px;
    padding: 0 16px;
    font-size: 16px;
    color: #333;
    transition: all 0.3s ease;
}

.custom-input:focus {
    outline: none;
    border-color: #0071e3;
    box-shadow: 0 0 0 2px rgba(0, 113, 227, 0.2);
}

.custom-input::placeholder {
    color: #999;
}

.error-message {
    position: absolute;
    color: #ff3b30;
    font-size: 12px;
    margin-top: 4px;
    left: 2px;
}

.login-button {
    height: 44px;
    width: 100%;
    background-color: #0071e3;
    color: #fff;
    border: none;
    border-radius: 10px;
    font-size: 16px;
    font-weight: 500;
    cursor: pointer;
    margin-top: 14px;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: background-color 0.2s ease;
}

.login-button:hover:not(:disabled) {
    background-color: #0077ed;
}

.login-button:active:not(:disabled) {
    background-color: #0062c3;
}

.login-button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

.button-loading {
    opacity: 0.8;
}

.divider {
    width: 100%;
    display: flex;
    align-items: center;
    margin: 30px 0;
    gap: 16px;
}

.divider-line {
    flex: 1;
    height: 1px;
    background-color: rgba(0, 0, 0, 0.1);
}

.divider-text {
    font-size: 14px;
    color: #777;
}

.create-account-button {
    width: 100%;
    height: 44px;
    background-color: #f5f5f5;
    color: #333;
    border: 1px solid #e0e0e0;
    border-radius: 10px;
    font-size: 16px;
    font-weight: 500;
    cursor: pointer;
    transition: background-color 0.2s ease;
}

.create-account-button:hover:not(:disabled) {
    background-color: #e8e8e8;
}

.create-account-button:active:not(:disabled) {
    background-color: #dadada;
}

.create-account-button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

.loading-spinner {
    display: inline-block;
    width: 18px;
    height: 18px;
    margin-right: 8px;
    border: 2px solid rgba(255, 255, 255, 0.3);
    border-radius: 50%;
    border-top-color: #fff;
    animation: spin 1s ease-in-out infinite;
}

@keyframes spin {
    to {
        transform: rotate(360deg);
    }
}

@media (max-width: 520px) {
    .login-card {
        max-width: 90%;
        padding: 30px 20px;
    }
}
</style>