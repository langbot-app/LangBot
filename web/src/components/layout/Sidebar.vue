<template>
    <v-navigation-drawer v-model="sidebarVisible" class="pt-4" width="160">
        <!-- 徽标和版本信息 -->
        <v-list-item id="logo-list-item">
            <template v-slot:prepend>
                <div id="logo-container">
                    <v-img id="logo-img" src="@/assets/langbot-logo-block.png" height="32" width="32"></v-img>
                    <div id="version-chip" v-tooltip="version + (debug ? ' (调试模式已启用)' : '')"
                        :style="{ 'background-color': debug ? '#27aa27' : '#1e9ae2' }">
                        {{ version }}
                    </div>
                </div>
            </template>
        </v-list-item>
        <v-divider></v-divider>

        <!-- 导航菜单项 -->
        <v-list density="compact" nav>
            <v-list-item to="/" :active="currentPath === '/'" prepend-icon="mdi-speedometer" title="仪表盘"
                v-tooltip="'仪表盘'"></v-list-item>
            <v-list-item to="/settings" :active="currentPath === '/settings'" prepend-icon="mdi-toggle-switch-outline"
                title="设置" v-tooltip="'设置'"></v-list-item>
            <v-list-item to="/logs" :active="currentPath === '/logs'" prepend-icon="mdi-file-outline" title="日志"
                v-tooltip="'日志'"></v-list-item>
            <v-list-item to="/plugins" :active="currentPath === '/plugins'" prepend-icon="mdi-puzzle-outline" title="插件"
                v-tooltip="'插件'"></v-list-item>
        </v-list>

        <!-- 底部附加功能区 -->
        <template v-slot:append>
            <div>
                <v-list density="compact" nav>
                    <!-- 任务列表对话框 -->
                    <v-dialog max-width="500" persistent v-model="taskDialogShow">
                        <template v-slot:activator="{ props: activatorProps }">
                            <v-list-item id="system-tasks-list-item" title="任务列表"
                                prepend-icon="mdi-align-horizontal-left" v-tooltip="'任务列表'" v-bind="activatorProps">
                            </v-list-item>
                        </template>

                        <template v-slot:default="{ isActive }">
                            <TaskDialog :dialog="{ show: isActive }" @close="closeTaskDialog" />
                        </template>
                    </v-dialog>

                    <!-- 系统信息菜单 -->
                    <v-list-item id="about-list-item" title="系统信息" prepend-icon="mdi-cog-outline" v-tooltip="'系统信息'">
                        <v-menu activator="parent" :close-on-content-click="false" location="end">
                            <v-list>
                                <v-list-item @click="showAboutDialog">
                                    <v-list-item-title>
                                        关于 LangBot
                                        <v-dialog max-width="400" persistent v-model="aboutDialogShow">
                                            <template v-slot:default="{ isActive }">
                                                <AboutDialog :dialog="{ show: isActive }" @close="closeAboutDialog" />
                                            </template>
                                        </v-dialog>
                                    </v-list-item-title>
                                </v-list-item>

                                <v-list-item @click="openDocs">
                                    <v-list-item-title>
                                        查看文档
                                    </v-list-item-title>
                                </v-list-item>

                                <v-list-item @click="reload('platform')">
                                    <v-list-item-title>
                                        重载消息平台
                                    </v-list-item-title>
                                </v-list-item>

                                <v-list-item @click="reload('plugin')">
                                    <v-list-item-title>
                                        重载插件
                                    </v-list-item-title>
                                </v-list-item>

                                <v-list-item @click="reload('provider')">
                                    <v-list-item-title>
                                        重载 LLM 管理器
                                    </v-list-item-title>
                                </v-list-item>

                                <v-divider></v-divider>

                                <v-list-item @click="handleLogout" color="error">
                                    <v-list-item-title class="text-error">
                                        退出登录
                                    </v-list-item-title>
                                </v-list-item>
                            </v-list>
                        </v-menu>
                    </v-list-item>
                </v-list>
            </div>
        </template>
    </v-navigation-drawer>
</template>

<script setup>
import { ref, computed, inject } from 'vue';
import { useRoute } from 'vue-router';
import { useStore } from 'vuex';
import TaskDialog from '@/components/TaskListDialog.vue';
import AboutDialog from '@/components/AboutDialog.vue';

const props = defineProps({
    modelValue: {
        type: Boolean,
        default: true
    }
});

const emit = defineEmits(['update:modelValue']);

const route = useRoute();
const store = useStore();

// 计算当前路径，用于高亮显示当前导航项
const currentPath = computed(() => route.path);

// 获取版本和调试模式信息
const version = computed(() => store.state.version);
const debug = computed(() => store.state.debug);

// 侧边栏可见性双向绑定
const sidebarVisible = computed({
    get: () => props.modelValue,
    set: (value) => emit('update:modelValue', value)
});

// 对话框控制
const taskDialogShow = ref(false);
const aboutDialogShow = ref(false);

// 任务对话框控制函数
function closeTaskDialog() {
    taskDialogShow.value = false;
}

// 关于对话框控制函数
function showAboutDialog() {
    aboutDialogShow.value = true;
}

function closeAboutDialog() {
    aboutDialogShow.value = false;
}

// 打开文档
function openDocs() {
    window.open('https://docs.langbot.app/insight/guide', '_blank');
}

// 系统重载功能
async function reload(scope) {
    try {
        await store.dispatch('reloadSystem', { scope });
        const message = `已重新加载${scope === 'platform' ? '消息平台' : scope === 'plugin' ? '插件' : 'LLM 管理器'}`;
        // 使用注入的snackbar，但需要在父组件中提供
        const snackbar = inject('snackbar', null);
        if (snackbar) {
            snackbar.success(message);
        }
    } catch (error) {
        const snackbar = inject('snackbar', null);
        if (snackbar) {
            snackbar.error(`重新加载失败: ${error.message}`);
        }
    }
}

// 登出函数
const handleLogout = () => {
    store.dispatch('logout');
};

// 暴露方法给父组件
defineExpose({
    closeTaskDialog,
    showAboutDialog,
    closeAboutDialog
});
</script>

<style scoped>
#logo-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    width: 100%;
    /* 确保容器占满整个列表项宽度 */
    margin: 0 auto;
    /* 水平居中 */
    position: relative;
    /* 为绝对定位的子元素提供参考点 */
}

#logo-list-item {
    margin-top: 0.5rem;
    margin-bottom: 1.5rem;
    display: flex;
    justify-content: center;
    /* 水平居中 */
    align-items: center;
    /* 垂直居中 */
    padding: 0;
    /* 移除默认内边距 */
}

#version-chip {
    position: absolute;
    top: calc(100% - 10px);
    /* 调整位置到logo下方 */
    left: 50%;
    /* 水平居中 */
    transform: translateX(-50%);
    /* 水平居中微调 */
    margin-top: 0.5rem;
    /* 与logo的间距 */
    font-size: 0.55rem;
    font-weight: 500;
    padding-inline: 0.4rem;
    text-align: center;
    color: white;
    border-radius: 0.5rem;
    border: 1px solid #fff;
    box-shadow: 0 0 0.1rem 0 rgba(0, 0, 0, 0.5);
    user-select: none;
    width: auto;
    /* 自适应内容宽度 */
    white-space: nowrap;
    /* 防止文本换行 */
}

#about-list-item:hover,
#system-tasks-list-item:hover {
    cursor: pointer;
    background-color: #eee;
}

#about-list-item:active,
#system-tasks-list-item:active {
    background-color: #ddd;
}
</style>