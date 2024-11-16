<template>
    <v-card class="about-dialog">

        <div id="content-container">
            <div id="logo-container">
                <v-img id="logo-img" src="@/assets/langbot-logo.png" width="64" />

                <div id="text-container">
                    <div id="title">
                        LangBot
                    </div>

                    <div id="subtitle">
                        版本 {{ proxy.$store.state.version }}
                    </div>

                    <div id="copyright">
                        版权所有 © 2024 RockChinQ
                    </div>
                </div>
            </div>
        </div>

        <template v-slot:actions>
            <v-btn id="open-source-btn" text="代码仓库" prepend-icon="mdi-github"
                @click="openSource"></v-btn>
            <v-btn class="ml-auto" text="关闭" prepend-icon="mdi-close" @click="close"></v-btn>
        </template>
    </v-card>
</template>

<script setup>
import { getCurrentInstance } from 'vue'

const { proxy } = getCurrentInstance()

const emit = defineEmits(['close'])

const close = () => {
    emit('close')
}

const openSource = () => {
    window.open('https://github.com/RockChinQ/LangBot', '_blank')
}
</script>

<style scoped>
.about-dialog {
    padding-top: 2rem;
}

#content-container {
    display: flex;
    flex-direction: column;
    align-items: center;
}

#logo-container {
    display: flex;
    flex-direction: column;
    align-items: center;
}

#logo-img {}

#text-container {
    display: flex;
    flex-direction: column;
    align-items: center;
}

#title {
    font-size: 1.2rem;
    margin-top: 0.5rem;
}

#subtitle {
    font-size: 0.6rem;
    color: #3c3c3c;
    margin-top: 0.2rem;
}

#copyright {
    font-size: 0.6rem;
    color: #3c3c3c;
    margin-top: 0.2rem;
    margin-bottom: 0.5rem;
}
</style>