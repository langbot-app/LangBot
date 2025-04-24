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
import { ref, inject, getCurrentInstance, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router' // 导入 useRoute 获取当前路由信息
import { useStore } from 'vuex'

// --- 常量定义 ---
const STORAGE_KEYS = {
    USER_TOKEN: 'user-token',
    SYSTEM_INITIALIZED: 'system-initialized'
}

// --- 依赖注入与实例 ---
const router = useRouter()
const route = useRoute() // 使用 useRoute 获取当前路由
const store = useStore()
const { proxy } = getCurrentInstance() // 保持原有方式，但建议后续重构为 provide/inject 或 import service
const snackbar = inject('snackbar')
const emit = defineEmits(['error', 'success', 'checkSystemInitialized'])

// --- 响应式状态 ---
const user = ref('')
const password = ref('')
const emailError = ref('')
const passwordError = ref('')
const isLoading = ref(false)
const isInitMode = ref(false) // 当前模式：false=登录, true=初始化
const systemInitialized = ref(null) // 存储从API获取的系统初始化状态

// --- 表单验证 ---
const validateEmail = () => {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    if (!user.value) {
        emailError.value = '邮箱不能为空'
        return false
    }
    if (!emailRegex.test(user.value)) {
        emailError.value = '请输入有效的邮箱地址'
        return false
    }
    emailError.value = '' // 清除错误
    return true
}

const validatePassword = () => {
    if (!password.value) {
        passwordError.value = '密码不能为空'
        return false
    }
    passwordError.value = '' // 清除错误
    return true
}

// 计算属性：表单是否有效（用于按钮禁用）
const isFormValid = computed(() => {
    // 确保值存在且没有错误信息
    return Boolean(user.value && password.value && !emailError.value && !passwordError.value)
})

// --- 模式切换 ---
const resetForm = () => {
    user.value = ''
    password.value = ''
    emailError.value = ''
    passwordError.value = ''
}

const toggleMode = () => {
    isInitMode.value = !isInitMode.value
    resetForm() // 重置表单

    // 更新路由（使用 replace 避免留下历史记录）
    router.replace(isInitMode.value ? '/init' : '/login')
}

// --- 核心逻辑：API 请求封装 (内部辅助函数) ---
// 这是一个简化的辅助函数，用于处理常见的加载状态和错误捕获
async function makeApiRequest(requestFn) {
    isLoading.value = true
    try {
        return await requestFn() // 执行传入的实际API请求函数
    } catch (err) {
        // 通用错误处理：记录日志
        console.error('API 请求出错:', err)
        const errorMessage = err.response?.data?.msg || '操作失败，请稍后重试'
        // 如果 snackbar 存在，显示错误（调用处可以覆盖此消息）
        if (snackbar) {
            snackbar.error(errorMessage)
        }
        // 将错误向上抛出，以便调用者可以进行特定处理
        throw err
    } finally {
        isLoading.value = false
    }
}

// --- 生命周期钩子 ---
onMounted(async () => {
    // 1. 根据当前路由确定初始模式
    isInitMode.value = route.path === '/init'

    // 2. 检查系统初始化状态
    try {
        // 使用辅助函数简化加载状态和基础错误处理
        const response = await makeApiRequest(() => proxy.$axios.get('/user/init'))

        if (response.data.code === 0) {
            const initialized = response.data.data.initialized
            systemInitialized.value = initialized // 存储状态
            localStorage.setItem(STORAGE_KEYS.SYSTEM_INITIALIZED, initialized ? 'true' : 'false')

            // 3. 根据初始化状态强制调整模式和路由
            if (!initialized && !isInitMode.value) {
                // 系统未初始化，但当前不在初始化页 -> 强制切换到初始化模式
                isInitMode.value = true
                router.replace('/init')
                resetForm() // 重置表单
            } else if (initialized && isInitMode.value) {
                // 系统已初始化，但当前在初始化页 -> 强制切换到登录模式
                isInitMode.value = false
                router.replace('/login')
                resetForm() // 重置表单
            }
        } else {
            // API 返回非 0 code 也视为一种错误情况
            snackbar.error(response.data.msg || '检查系统状态失败')
            systemInitialized.value = null; // 状态未知
        }
    } catch (error) {
        // makeApiRequest 已经处理了基础错误日志和可能的 snackbar 提示
        systemInitialized.value = null; // 标记状态为未知
        // 这里可以根据需要添加更具体的错误处理逻辑
        console.error('检查系统初始化状态时捕获到错误', error)
    }
})

// --- 处理登录 ---
const handleLogin = async () => {
    // 主动触发验证，确保即使用户绕过禁用也能验证
    const isEmailValid = validateEmail()
    const isPasswordValid = validatePassword()
    if (!isEmailValid || !isPasswordValid) return // 如果验证失败则中止

    try {
        const response = await makeApiRequest(() => proxy.$axios.post('/user/auth', {
            user: user.value,
            password: password.value
        }))

        if (response.data.code === 0) {
            const token = response.data.data.token
            localStorage.setItem(STORAGE_KEYS.USER_TOKEN, token)
            proxy.$axios.defaults.headers.common['Authorization'] = `Bearer ${token}`
            store.commit('setUserToken', token)
            snackbar.success('登录成功')

            // 检查token有效性
            await checkTokenValidity()

            router.push('/') // 导航到主页
        } else {
            snackbar.error(response.data.msg || '登录失败')
        }
    } catch (error) {
        // makeApiRequest 内部已处理通用错误，这里可以添加特定于登录失败的逻辑
        const specificErrorMessage = error.response?.data?.msg || '登录时发生未知错误';
        if (snackbar && specificErrorMessage !== '操作失败，请稍后重试') { // 避免重复显示通用消息
            snackbar.error(specificErrorMessage);
        }
    }
}

// --- 检查 Token 有效性 ---
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

// --- 处理系统初始化 ---
const initialize = async () => {
    // 主动触发验证
    const isEmailValid = validateEmail()
    const isPasswordValid = validatePassword()
    if (!isEmailValid || !isPasswordValid) return

    // 优化点：使用 onMounted 中获取的状态，避免冗余 API 调用
    if (systemInitialized.value === true) {
        snackbar.error('系统已初始化，不允许重复注册管理员账户')
        // 短暂延迟后跳转到登录页
        setTimeout(() => {
            if (isInitMode.value) { // 再次检查，防止状态变化
                toggleMode(); // 切换到登录模式并更新路由
            }
        }, 1500)
        return // 阻止后续初始化操作
    }

    // 如果 systemInitialized 为 null (检查失败)，可以选择提示用户
    if (systemInitialized.value === null) {
        snackbar.error('系统状态未知，请刷新页面或稍后再试');
        return;
    }

    try {
        // 使用辅助函数发起初始化请求
        const res = await makeApiRequest(() => proxy.$axios.post('/user/init', {
            user: user.value,
            password: password.value
        }))

        if (res.data.code === 0) { // 确保响应成功
            emit('success', '系统初始化成功')
            emit('checkSystemInitialized') // 通知父组件检查状态（如果需要）
            snackbar.success('系统初始化成功')

            // 更新本地状态和 localStorage
            systemInitialized.value = true; // 更新组件内部状态
            localStorage.setItem(STORAGE_KEYS.SYSTEM_INITIALIZED, 'true')

            // 初始化成功后短暂延迟跳转到登录界面
            setTimeout(() => {
                if (isInitMode.value) { // 再次检查，防止状态变化
                    toggleMode(); // 切换到登录模式并更新路由
                }
            }, 1000)
        } else {
            // API 返回业务错误
            snackbar.error(res.data.msg || '系统初始化失败')
            emit('error', res.data.msg || '系统初始化失败')
        }
    } catch (err) {
        // makeApiRequest 已处理通用错误日志和 snackbar 提示
        const specificErrorMessage = err.response?.data?.msg || '系统初始化时发生未知错误';
        emit('error', specificErrorMessage);
        // 确保 snackbar 显示具体的错误信息（如果不同于通用信息）
        if (snackbar && specificErrorMessage !== '操作失败，请稍后重试') {
            snackbar.error(specificErrorMessage);
        }
    }
}

// --- 监听路由变化以同步模式 ---
// 如果用户通过浏览器前进/后退按钮改变了 /login 和 /init 之间的路由
// 需要确保 isInitMode 的状态与路由同步
watch(() => route.path, (newPath) => {
    const targetMode = newPath === '/init';
    if (isInitMode.value !== targetMode) {
        // 如果模式与路由不符，更新模式
        isInitMode.value = targetMode;
        // 这里可以选择是否重置表单，取决于产品需求
        // resetForm();
    }
})
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