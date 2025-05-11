<template>
    <div id="number-field-data">
        <div class="number-field-data-item" :style="{ color: color }">
            {{ number }}
        </div>

        <div class="number-field-data-item-title" :style="{ marginTop: link ? '0rem' : '0.1rem', fontSize: link ? '0.9rem' : '1.1rem', marginBottom: link ? '0rem' : '0.5rem' }">
            {{ title }}
        </div>
        <button class="number-field-data-item-link-text" v-if="link" @click="linkClick">{{ linkText }}</button>
    </div>
</template>

<script setup>
const props = defineProps({
    title: {
        type: String,
        required: true
    },
    number: {
        type: Number,
        required: true
    },
    color: {
        type: String,
        default: '#4271bf'
    },
    link: {
        type: String,
        default: ''
    },
    linkText: {
        type: String,
        default: '查看详情'
    }
})

import { getCurrentInstance } from 'vue'

const { proxy } = getCurrentInstance()

const linkClick = (e) => {
    proxy.$router.push(props.link)
}
</script>

<style scoped>

#number-field-data {
    display: flex;
    flex-direction: column;
    align-items: center;
    /* justify-content: center; */
}

.number-field-data-item {
    font-size: 2.2rem;
    font-weight: 600;
    user-select: none;
}

.number-field-data-item-title {
    font-weight: 600;
    user-select: none;
}

.number-field-data-item-link-text {
    text-decoration: none;
    appearance: none;
    font-weight: 600;
    color: #4271bf;
    font-size: 0.6rem;
}

</style>