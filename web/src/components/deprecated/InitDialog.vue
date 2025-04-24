<template>
    <div class="login-container">
        <div class="login-card">
            <div class="login-icon">
                <img src="@/assets/langbot-logo.png" alt="LangBot Logo" />
            </div>
            <div class="sign-in-label">系统初始化</div>

            <div class="instruction-text">
                请输入初始管理员邮箱和密码
            </div>

            <form ref="initForm" @submit.prevent="initialize" class="login-form">
                <div class="input-group">
                    <input id="email" v-model="user" type="email" placeholder="管理员邮箱" :disabled="isLoading"
                        @blur="validateEmail" required class="custom-input" />
                    <div class="error-message" v-if="emailError">{{ emailError }}</div>
                </div>

                <div class="input-group">
                    <input id="password" v-model="password" type="password" placeholder="管理员密码" :disabled="isLoading"
                        @keyup.enter="initialize" required class="custom-input" />
                    <div class="error-message" v-if="passwordError">{{ passwordError }}</div>
                </div>

                <button type="submit" class="login-button" :disabled="isLoading || !isFormValid"
                    :class="{ 'button-loading': isLoading }">
                    <span v-if="isLoading" class="loading-spinner"></span>
                    <span>初始化</span>
                </button>
            </form>

            <div class="divider">
                <span class="divider-line"></span>
                <span class="divider-text">或</span>
                <span class="divider-line"></span>
            </div>

            <div class="back-to-login">
                <button type="button" class="create-account-button" @click="goToLogin" :disabled="isLoading">
                    返回登录
                </button>
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref, inject, getCurrentInstance, computed } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const { proxy } = getCurrentInstance()

const emit = defineEmits(['error', 'success', 'checkSystemInitialized'])

const user = ref('')
const password = ref('')
const emailError = ref('')
const passwordError = ref('')
const isLoading = ref(false)
const initForm = ref(null)

const snackbar = inject('snackbar')

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

const goToLogin = () => {
    router.push('/login')
}

const initialize = async () => {
    // 表单验证
    const isEmailValid = validateEmail()
    const isPasswordValid = validatePassword()

    if (!isEmailValid || !isPasswordValid) return

    isLoading.value = true

    try {
        // 先检查系统是否已初始化
        const checkResponse = await proxy.$axios.get('/user/init')
        if (checkResponse.data.code === 0 && checkResponse.data.data.initialized) {
            snackbar.error('系统已初始化，不允许重复注册管理员账户')
            isLoading.value = false
            setTimeout(() => {
                router.push('/login')
            }, 1500)
            return
        }

        // 发送初始化请求
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
    margin-bottom: 10px;
    color: #333;
}

.instruction-text {
    font-size: 14px;
    color: #666;
    margin-bottom: 20px;
    text-align: center;
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
    margin-bottom: 10px;
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
    display: flex;
    align-items: center;
    width: 100%;
    margin: 20px 0;
}

.divider-line {
    flex-grow: 1;
    height: 1px;
    background-color: #e0e0e0;
}

.divider-text {
    margin: 0 10px;
    color: #666;
    font-size: 14px;
}

.back-to-login {
    width: 100%;
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
