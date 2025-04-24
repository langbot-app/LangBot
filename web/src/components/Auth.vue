<template>
    <div class="auth-container">
        <div class="auth-card">
            <div class="auth-icon">
                <img src="@/assets/langbot-logo.png" alt="LangBot Logo" />
            </div>
            <div class="sign-in-label">{{ isInitMode ? '系统初始化' : '通过 LangBot 账户登录' }}</div>

            <!-- 初始化模式的说明文本 -->
            <div v-if="isInitMode" class="instruction-text">
                请输入初始管理员邮箱和密码
            </div>

            <!-- 修正：不使用表单提交方式，改为点击按钮直接调用方法 -->
            <div class="auth-form">
                <div class="input-group">
                    <input id="email" v-model="user" type="email" :placeholder="isInitMode ? '管理员邮箱' : '电子邮件'"
                        :disabled="isLoading" @blur="validateEmail" required class="custom-input" />
                    <div class="error-message" v-if="emailError">{{ emailError }}</div>
                </div>

                <div class="input-group">
                    <input id="password" v-model="password" type="password" :placeholder="isInitMode ? '管理员密码' : '密码'"
                        :disabled="isLoading" @keyup.enter="isInitMode ? initialize() : handleLogin()" required
                        class="custom-input" />
                    <div class="error-message" v-if="passwordError">{{ passwordError }}</div>
                </div>

                <!-- 修正：直接调用方法，不依赖表单提交 -->
                <button type="button" class="auth-button" :disabled="isLoading || !isFormValid"
                    :class="{ 'button-loading': isLoading }" @click="isInitMode ? initialize() : handleLogin()">
                    <span v-if="isLoading" class="loading-spinner"></span>
                    <span>{{ isInitMode ? '初始化' : '继续' }}</span>
                </button>
            </div>

            <div class="divider">
                <span class="divider-line"></span>
                <span class="divider-text">或</span>
                <span class="divider-line"></span>
            </div>

            <div class="switch-auth-mode">
                <button type="button" class="switch-mode-button" @click="toggleMode" :disabled="isLoading">
                    {{ isInitMode ? '返回登录' : '创建 LangBot 账户' }}
                </button>
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref, inject, getCurrentInstance, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useStore } from 'vuex'

const router = useRouter()
const store = useStore()
const { proxy } = getCurrentInstance()

const emit = defineEmits(['error', 'success', 'checkSystemInitialized'])

// 响应式状态
const user = ref('')
const password = ref('')
const emailError = ref('')
const passwordError = ref('')
const isLoading = ref(false)
const authForm = ref(null)
const isInitMode = ref(false) // 控制当前模式：登录还是初始化

const snackbar = inject('snackbar')

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

// 切换登录/初始化模式
const toggleMode = () => {
    isInitMode.value = !isInitMode.value
    // 切换模式时重置表单
    user.value = ''
    password.value = ''
    emailError.value = ''
    passwordError.value = ''

    // 更新路由，但不触发完整页面导航
    router.replace(isInitMode.value ? '/init' : '/login', { replace: true })
}

// 组件加载时根据路由设置当前模式
onMounted(async () => {
    // 根据当前路由确定模式
    console.log('当前路径:', router.currentRoute.value.path);
    isInitMode.value = router.currentRoute.value.path === '/init'
    console.log('初始化模式:', isInitMode.value);

    try {
        // 检查系统是否已初始化
        const response = await proxy.$axios.get('/user/init')
        if (response.data.code === 0) {
            const initialized = response.data.data.initialized
            localStorage.setItem('system-initialized', initialized ? 'true' : 'false')
            console.log('系统已初始化:', initialized);

            // 如果系统未初始化，自动切换到初始化模式
            if (!initialized && !isInitMode.value) {
                isInitMode.value = true
                router.replace('/init')
            }
            // 如果系统已初始化但用户在初始化页面，则跳转到登录页面
            else if (initialized && isInitMode.value) {
                isInitMode.value = false
                router.replace('/login')
            }
        }
    } catch (error) {
        console.error('检查系统初始化状态失败', error)
    }
})

// ======= 处理登录 =======
const handleLogin = async () => {
    console.log('点击登录按钮');

    // 表单验证
    const isEmailValid = validateEmail()
    const isPasswordValid = validatePassword()

    console.log('邮箱验证:', isEmailValid, '密码验证:', isPasswordValid);

    if (!isEmailValid || !isPasswordValid) return

    try {
        console.log('开始登录请求...');
        isLoading.value = true
        const response = await proxy.$axios.post('/user/auth', {
            user: user.value,
            password: password.value
        })

        console.log('登录响应:', response);

        if (response.data.code === 0) {
            // 登录成功处理
            const token = response.data.data.token
            console.log('获取到令牌');

            // 存储令牌并设置全局请求头
            localStorage.setItem('user-token', token)
            proxy.$axios.defaults.headers.common['Authorization'] = `Bearer ${token}`

            // 更新状态并验证令牌
            store.commit('setUserToken', token)
            snackbar.success('登录成功')

            // 检查token有效性
            await checkTokenValidity()
            console.log('令牌检查完成');

            // 登录成功后导航到主页
            console.log('准备跳转到主页');
            router.push('/')
        } else {
            console.error('登录失败:', response.data.msg);
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

// ======= 处理系统初始化 =======
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
                isInitMode.value = false
                router.replace('/login')
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
            isInitMode.value = false
            router.replace('/login')
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
.auth-container {
    display: flex;
    justify-content: center;
    align-items: center;
    min-height: 100vh;
    background-color: #f6f6f6;
    color: #333;
    font-family: SF Pro Text, Helvetica Neue, sans-serif;
    -webkit-font-smoothing: antialiased;
}

.auth-card {
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

.auth-icon {
    width: 70px;
    height: 70px;
    margin-bottom: 20px;
    display: flex;
    justify-content: center;
    align-items: center;
}

.auth-icon img {
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

.auth-form {
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

.auth-button {
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

.auth-button:hover:not(:disabled) {
    background-color: #0077ed;
}

.auth-button:active:not(:disabled) {
    background-color: #0062c3;
}

.auth-button:disabled {
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

.switch-auth-mode {
    width: 100%;
}

.switch-mode-button {
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

.switch-mode-button:hover:not(:disabled) {
    background-color: #e8e8e8;
}

.switch-mode-button:active:not(:disabled) {
    background-color: #dadada;
}

.switch-mode-button:disabled {
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
    .auth-card {
        max-width: 90%;
        padding: 30px 20px;
    }
}
</style>