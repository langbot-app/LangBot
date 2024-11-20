<template>
    <v-dialog v-model="dialog" width="350" persistent>
        <v-card id="login-dialog">
            <v-card-title class="d-flex align-center" style="gap: 0.5rem;">
                <img src="@/assets/langbot-logo.png" height="32" width="32" />
                <span>登录 LangBot</span>
            </v-card-title>

            <v-card-text class="d-flex flex-column" style="gap: 0.5rem;margin-bottom: -2rem;margin-top: 1rem;">
                
                <v-text-field v-model="user" variant="outlined" label="邮箱" :rules="[rules.required, rules.email]"
                    clearable />
                <v-text-field v-model="password" variant="outlined" label="密码" :rules="[rules.required]"
                    type="password" clearable />
            </v-card-text>

            <v-card-actions>
                <v-btn color="primary" variant="flat" @click="login">登录</v-btn>
            </v-card-actions>
        </v-card>
    </v-dialog>
</template>

<script setup>
import { ref, getCurrentInstance } from 'vue'

const { proxy } = getCurrentInstance()

const emit = defineEmits(['error', 'success', 'checkToken'])

const dialog = ref(true)

const user = ref('')
const password = ref('')

const rules = {
    required: value => !!value || '必填项',
    email: value => {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
        return emailRegex.test(value) || '请输入有效的邮箱地址'
    }
}


const login = () => {
    proxy.$axios.post('/user/auth', {
        user: user.value,
        password: password.value
    }).then(res => {
        if (res.data.code == 0) {
            emit('success', '登录成功')
            localStorage.setItem('user-token', res.data.data.token)
            setTimeout(() => {
                location.reload()
            }, 1000)
        } else {
            emit('error', res.data.msg)
        }
    }).catch(err => {
        if (err.response.data.msg) {
            emit('error', err.response.data.msg)
        } else {
            emit('error', '登录失败')
        }
    })
}

</script>

<style scoped>
#login-dialog {
    padding-top: 0.8rem;
    padding-bottom: 0.5rem;
    padding-inline: 0.5rem;
}
</style>