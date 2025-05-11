<template>
    <span class="title-container"> 
        <h2 id="page-title">{{ title }}</h2>
        <v-icon @click="refresh" id="refresh-icon" icon="mdi-refresh" />
    </span>
</template>

<script setup>
defineProps({
    title: {
        type: String,
        required: true
    }
})

const emit = defineEmits(['refresh'])

const refresh = () => {
    emit('refresh')
}

</script>

<style scoped>
#page-title {
    font-weight: 500;
    margin-left: 1.4rem;
    user-select: none;
}

.title-container {
    display: flex;
    justify-content: flex-start;
    align-items: center;
    padding-top: 1rem;
}

#refresh-icon {
    padding-top: 0.1rem;
    margin-left: 0.5rem;
    color: #aaa;
}

#refresh-icon:hover {
    cursor: pointer;
}

#refresh-icon:active {
    color: #6c6c6c;
}
</style>