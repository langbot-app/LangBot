<template>
    <div class="plugin-card">
        <div class="plugin-card-header">
            <div class="plugin-id">
                <div class="plugin-card-author">{{ plugin.author }} /</div>
                <div class="plugin-card-title">{{ plugin.name }}</div>
            </div>
            <div class="plugin-card-badges">
                <v-icon class="plugin-github-source" icon="mdi-github" v-if="plugin.repository != ''"
                    @click="openGithubSource"></v-icon>
            </div>
        </div>
        <div class="plugin-card-description" >{{ plugin.description }}</div>

        <div class="plugin-card-brief-info">
            <div class="plugin-card-brief-info-item">
                <v-icon id="plugin-stars-icon" icon="mdi-star" />
                <div id="plugin-stars-count">{{ plugin.stars }}</div>
            </div>
            <v-btn color="primary" @click="installPlugin" density="compact">安装</v-btn>
        </div>
    </div>
</template>

<script setup>
const props = defineProps({
    plugin: {
        type: Object,
        required: true
    },
});

const emit = defineEmits(['install']);

const openGithubSource = () => {
    window.open("https://"+props.plugin.repository, '_blank');
}

const installPlugin = () => {
    emit('install', props.plugin);
}

</script>

<style scoped>
.plugin-card {
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    padding: 0.8rem;
    padding-left: 1rem;
    margin: 1rem 0;
    background-color: white;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    height: 10rem;
}

.plugin-card-header {
    display: flex;
    flex-direction: row;
    justify-content: space-between;
}

.plugin-card-author {
    font-size: 0.8rem;
    color: #666;
    font-weight: 500;
    user-select: none;
}

.plugin-card-title {
    font-size: 0.9rem;
    font-weight: 600;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    user-select: none;
}

.plugin-card-description {
    font-size: 0.7rem;
    color: #666;
    font-weight: 500;
    margin-top: -1rem;
    height: 2rem;
    /* 超出部分自动换行，最多两行 */
    text-overflow: ellipsis;
    overflow-y: hidden;
    white-space: wrap;
    user-select: none;
}

.plugin-card-badges {
    display: flex;
    flex-direction: row;
    gap: 0.5rem;
}

.plugin-github-source {
    cursor: pointer;
    color: #222;
    font-size: 1.3rem;
}

.plugin-disabled {
    font-size: 0.7rem;
    font-weight: 500;
    height: 1.3rem;
    padding-inline: 0.4rem;
    user-select: none;
}


.plugin-card-brief-info {
    display: flex;
    flex-direction: row;
    justify-content: space-between;
    /* background-color: #f0f0f0; */
    gap: 0.8rem;
    margin-left: -0.2rem;
    margin-bottom: 0rem;
}

.plugin-card-events {
    display: flex;
    flex-direction: row;
    gap: 0.4rem;
}

.plugin-card-events-icon {
    font-size: 1.8rem;
    color: #666;
}

.plugin-card-events-count {
    font-size: 1.2rem;
    font-weight: 600;
    color: #666;
}

.plugin-card-functions {
    display: flex;
    flex-direction: row;
    gap: 0.4rem;
}

.plugin-card-functions-icon {
    font-size: 1.6rem;
    color: #666;
}

.plugin-card-functions-count {
    font-size: 1.2rem;
    font-weight: 600;
    color: #666;
}

.plugin-card-brief-info-item {
    display: flex;
    flex-direction: row;
    gap: 0.4rem;
}

#plugin-stars-icon {
    color: #0073ff;
}

#plugin-stars-count {
    margin-top: 0.1rem;
    font-weight: 700;
    color: #0073ff;
    user-select: none;
}

.plugin-card-brief-info-item:hover .plugin-card-brief-info-item-icon {
    color: #333;
}


</style>
