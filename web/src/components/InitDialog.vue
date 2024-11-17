<template>
    <v-dialog v-model="dialog" width="500" persistent>
        <v-card id="init-dialog">
            <v-card-title class="d-flex align-center" style="gap: 0.5rem;">
                <img src="@/assets/langbot-logo.png" height="32" width="32" />
                <span>系统初始化</span>
            </v-card-title>

            <v-card-text>
                <p>请输入初始管理员邮箱和密码。</p>
            </v-card-text>

            <v-card-text class="d-flex flex-column" style="gap: 0.5rem;">
                <v-text-field v-model="user" variant="outlined" label="管理员邮箱" :rules="[rules.required, rules.email]"
                    clearable />
                <v-text-field v-model="password" variant="outlined" label="管理员密码" :rules="[rules.required]"
                    type="password" clearable />
            </v-card-text>

            <v-card-actions>
                <v-btn color="primary" variant="flat" @click="initialize" prepend-icon="mdi-check">初始化</v-btn>
            </v-card-actions>
        </v-card>
    </v-dialog>
</template>

<script setup>
import { ref, inject, getCurrentInstance } from 'vue'

const { proxy } = getCurrentInstance()

const emit = defineEmits(['error', 'success', 'checkSystemInitialized'])

const dialog = ref(true)

const user = ref('')
const password = ref('')

const snackbar = inject('snackbar')

const rules = {
    required: value => !!value || '必填项',
    email: value => {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
        return emailRegex.test(value) || '请输入有效的邮箱地址'
    }
}


function checkEmailValid(email) {
    const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    return regex.test(email)
}

const initialize = () => {
    // 检查邮箱和密码是否为空
    if (user.value == undefined || password.value == undefined) {
        emit('error', '邮箱和密码不能为空')
        return
    }

    if (user.value == '' || password.value == '') {
        emit('error', '邮箱和密码不能为空')
        return
    }

    if (!checkEmailValid(user.value)) {
        emit('error', '请输入有效的邮箱地址')
        return
    }

    proxy.$axios.post('/user/init', {
        user: user.value,
        password: password.value
    }).then(res => {
        emit('success', '系统初始化成功')

        emit('checkSystemInitialized')
    })
}
</script>

<style scoped>
#init-dialog {
    padding-top: 0.8rem;
    padding-inline: 0.5rem;
}
</style>
