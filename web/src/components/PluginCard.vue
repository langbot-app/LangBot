<template>
    <div class="plugin-card">
        <div class="plugin-card-header">
            <div class="plugin-id">
                <div class="plugin-card-author">{{ plugin.author }} /</div>
                <div class="plugin-card-title">{{ plugin.name }}</div>
            </div>
            <div class="plugin-card-badges">
                <v-icon class="plugin-github-source" icon="mdi-github" v-if="plugin.source != ''"
                    @click="openGithubSource"></v-icon>
                <v-chip class="plugin-disabled" v-if="!plugin.enabled" color="error" variant="outlined"
                    density="compact">已禁用</v-chip>
                <v-chip class="plugin-version" color="primary" density="compact" variant="flat">v{{ plugin.version
                    }}</v-chip>
            </div>
        </div>
        <div class="plugin-card-description">{{ plugin.description }}</div>

        <div class="plugin-card-brief-info">
            <div class="plugin-card-brief-info-item">
                <v-tooltip text="已注册的事件处理器" location="bottom">
                    <template v-slot:activator="{ props }">
                        <div class="plugin-card-events" v-bind="props">
                            <v-icon class="plugin-card-events-icon" icon="mdi-link-box-variant-outline" />
                            <div class="plugin-card-events-count">{{ Object.keys(plugin.event_handlers).length }}</div>
                        </div>
                    </template>
                </v-tooltip>
                <v-tooltip text="已注册的内容函数" location="bottom">
                    <template v-slot:activator="{ props }">
                        <div class="plugin-card-functions" v-bind="props">
                            <v-icon class="plugin-card-functions-icon" icon="mdi-tools" />
                            <div class="plugin-card-functions-count">{{ plugin.content_functions.length }}</div>
                        </div>
                    </template>
                </v-tooltip>
            </div>
            <v-menu class="plugin-card-menu">
                <template v-slot:activator="{ props }">
                    <v-icon class="plugin-card-menu-btn" icon="mdi-cog" v-bind="props" variant="text"  size="small"/>
                </template>
                <v-list>
                    <template v-for="item in menuItems" :key="item.title">
                        <v-list-item v-if="item.condition(plugin)" @click="item.action">
                            <v-list-item-title>{{ item.title }}</v-list-item-title>
                        </v-list-item>
                    </template>
                </v-list>
            </v-menu>
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

const emit = defineEmits(['toggle', 'update', 'uninstall']);

const openGithubSource = () => {
    window.open(props.plugin.source, '_blank');
}

const togglePlugin = () => {
    emit('toggle', props.plugin);
}

const updatePlugin = () => {
    emit('update', props.plugin);
}

const uninstallPlugin = () => {
    emit('uninstall', props.plugin);
}

const menuItems = [
    {
        title: '禁用',
        condition: (plugin) => plugin.enabled,
        action: togglePlugin
    },
    {
        title: '启用',
        condition: (plugin) => !plugin.enabled,
        action: togglePlugin
    },
    {
        title: '更新',
        condition: (plugin) => plugin.source != '',
        action: updatePlugin
    },
    {
        title: '删除',
        condition: (plugin) => true,
        action: uninstallPlugin
    }
]
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
    font-size: 1.1rem;
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
    margin-top: 0rem;
    height: 2rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
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

.plugin-version {
    font-size: 0.7rem;
    font-weight: 700;
    height: 1.3rem;
    padding-inline: 0.5rem;
    user-select: none;
}

.plugin-card-brief-info {
    display: flex;
    flex-direction: row;
    justify-content: space-between;
    /* background-color: #f0f0f0; */
    gap: 0.8rem;
    margin-left: -0.2rem;
    margin-top: 0.5rem;
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

.plugin-card-brief-info-item:hover {
    cursor: pointer;
}

.plugin-card-brief-info-item:hover .plugin-card-brief-info-item-icon {
    color: #333;
}

.plugin-card-menu {
    margin-top: 0.5rem;
}

.plugin-card-menu-btn {
    font-size: 1.4rem;
    margin-top: 0.2rem;
    font-weight: 400;
    padding: 0rem;
    color: #3265ba;
}

.plugin-card-menu-btn:hover {
    color: #4271bf;
}

.plugin-card-menu-btn:active {
    color: rgb(0, 47, 104);
}

</style>
