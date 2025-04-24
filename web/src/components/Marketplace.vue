<template>
    <div id="marketplace-container">
        <div id="marketplace-search-bar">

            <span style="width: 14rem;">
                <v-text-field id="marketplace-search-bar-search-input" variant="solo" v-model="searchQuery" label="搜索"
                    density="compact" @update:model-value="updateSearch" />
            </span>
            <!--下拉选择排序-->
            <span style="width: 10rem;">
                <v-select id="marketplace-search-bar-sort-select" v-model="sort" :items="sortItems" variant="solo"
                    label="排序" density="compact" @update:model-value="updateSort" />
            </span>
            <span style="margin-left: 1rem;">
                <div id="marketplace-search-bar-total-plugins-count">
                    共 {{ totalPluginsCount }} 个插件
                </div>
            </span>
            <span style="margin-left: 1rem;">
                <!-- 分页 -->
                <v-pagination style="width: 14rem;" v-model="currentPage" :length="totalPages" variant="solo"
                    density="compact" total-visible="4" @update:model-value="updatePage" />
            </span>
        </div>
        <div id="marketplace-plugins-container" ref="pluginsContainer">
            <div v-if="isLoading" class="loading-indicator">
                <v-progress-circular indeterminate color="primary"></v-progress-circular>
                <span class="ml-2">加载中...</span>
            </div>
            <div v-else-if="fetchError" class="error-message">{{ fetchError }}</div>
            <div v-else-if="storePlugins.length === 0" class="no-data-message">没有找到插件</div>
            <div v-else id="marketplace-plugins-grid">
                <MarketPluginCard v-for="plugin in storePlugins" :key="plugin.id" :plugin="plugin"
                    @install="installPlugin" />
            </div>
        </div>
    </div>
</template>

<script setup>
import MarketPluginCard from './MarketPluginCard.vue'
import { ref, getCurrentInstance, onMounted, onUnmounted, computed } from 'vue'
import { inject } from "vue";

const snackbar = inject('snackbar');
const { proxy } = getCurrentInstance()
const pluginsContainer = ref(null)
const isLoading = ref(false);
const fetchError = ref(null);

// 使用计算属性获取 store 中的数据，避免直接访问
const storePlugins = computed(() => proxy.$store.state.marketplacePlugins);
const totalPluginsCount = computed(() => proxy.$store.state.marketplaceTotalPluginsCount);
const totalPages = computed(() => proxy.$store.state.marketplaceTotalPages);

// 本地数据绑定
const searchQuery = ref(proxy.$store.state.marketplaceParams.query);
const currentPage = ref(proxy.$store.state.marketplaceParams.page);

const sortItems = [
    '最近新增',
    '最多星标',
    '最近更新',
]

const sortParams = {
    '最近新增': {
        sort_by: 'created_at',
        sort_order: 'DESC',
    },
    '最多星标': {
        sort_by: 'stars',
        sort_order: 'DESC',
    },
    '最近更新': {
        sort_by: 'pushed_at',
        sort_order: 'DESC',
    }
}

const sort = ref(sortItems[0])

// 更新排序参数并获取数据
const updateSort = (value) => {
    proxy.$store.state.marketplaceParams.sort_by = sortParams[value].sort_by;
    proxy.$store.state.marketplaceParams.sort_order = sortParams[value].sort_order;
    proxy.$store.state.marketplaceParams.page = 1;
    currentPage.value = 1; // 同步本地页码状态

    fetchMarketplacePlugins();
}

// 更新页码并获取数据
const updatePage = (value) => {
    proxy.$store.state.marketplaceParams.page = value;
    fetchMarketplacePlugins();
}

// 简单的 debounce 实现
const debounce = (fn, delay) => {
    let timer = null;
    return function (...args) {
        if (timer) clearTimeout(timer);
        timer = setTimeout(() => {
            fn.apply(this, args);
            timer = null;
        }, delay);
    };
}

// 带 debounce 的搜索处理
const updateSearch = debounce((value) => {
    proxy.$store.state.marketplaceParams.query = value;
    searchQuery.value = value; // 保证本地状态同步
    proxy.$store.state.marketplaceParams.page = 1;
    currentPage.value = 1;
    fetchMarketplacePlugins();
}, 500); // 500ms 延迟，避免频繁请求

// 优化每页插件数量的计算
const calculatePluginsPerPage = () => {
    if (!pluginsContainer.value) return 10;

    const containerWidth = pluginsContainer.value.clientWidth;
    const containerHeight = pluginsContainer.value.clientHeight;

    // 卡片尺寸计算
    const cardWidth = 18 * 16 + 16;
    const cardHeight = 9 * 16 + 16;

    const cardsPerRow = Math.max(1, Math.floor(containerWidth / cardWidth));
    const rows = Math.max(1, Math.floor(containerHeight / cardHeight));

    return Math.max(1, cardsPerRow * rows);
}

// 带异常处理的数据获取
const fetchMarketplacePlugins = async () => {
    if (isLoading.value) return; // 防止重复请求

    isLoading.value = true;
    fetchError.value = null;

    try {
        // 获取最新的每页数量
        const perPage = calculatePluginsPerPage();
        proxy.$store.state.marketplaceParams.per_page = perPage;

        const response = await proxy.$axios.post('https://space.langbot.app/api/v1/market/plugins', {
            query: proxy.$store.state.marketplaceParams.query,
            sort_by: proxy.$store.state.marketplaceParams.sort_by,
            sort_order: proxy.$store.state.marketplaceParams.sort_order,
            page: proxy.$store.state.marketplaceParams.page,
            page_size: perPage,
        });

        if (response.data.code != 0) {
            throw new Error(response.data.msg || '获取插件列表失败');
        }

        // 高效处理插件数据
        const processedPlugins = response.data.data.plugins.map(plugin => {
            const parts = plugin.repository.split('/');
            return {
                ...plugin,
                name: parts.length >= 3 ? parts[2] : '未知名称',
                author: parts.length >= 2 ? parts[1] : '未知作者'
            };
        });

        proxy.$store.state.marketplacePlugins = processedPlugins;
        proxy.$store.state.marketplaceTotalPluginsCount = response.data.data.total;
        proxy.$store.state.marketplaceTotalPages = Math.ceil(response.data.data.total / perPage) || 1;
    } catch (error) {
        console.error('获取插件市场数据失败:', error);
        fetchError.value = typeof error === 'string' ? error : error.message || '网络错误';
        snackbar.error(fetchError.value);
    } finally {
        isLoading.value = false;
    }
}

// 带 debounce 的resize处理函数
const handleResize = debounce(() => {
    const oldPerPage = proxy.$store.state.marketplaceParams.per_page;
    const newPerPage = calculatePluginsPerPage();

    // 只有当每页数量变化时才重新获取数据
    if (oldPerPage !== newPerPage) {
        proxy.$store.state.marketplaceParams.per_page = newPerPage;
        fetchMarketplacePlugins();
    }
}, 300); // 300ms 延迟

onMounted(() => {
    calculatePluginsPerPage();
    fetchMarketplacePlugins();

    // 添加 resize 监听，使用 debounce 处理函数
    window.addEventListener('resize', handleResize);
})

onUnmounted(() => {
    // 移除监听器，防止内存泄漏
    window.removeEventListener('resize', handleResize);
})

const emit = defineEmits(['installPlugin'])

const installPlugin = (plugin) => {
    emit('installPlugin', plugin.repository)
}
</script>

<style scoped>
#marketplace-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    width: 100%;
    height: 100%;
}

#marketplace-search-bar {
    display: flex;
    flex-direction: row;
    margin-top: 1rem;
    padding-right: 1rem;
    gap: 1rem;
    width: 100%;
    align-items: center;
}

#marketplace-search-bar-search-input {
    position: relative;
    left: 1rem;
    width: 10rem;
}

#marketplace-search-bar-total-plugins-count {
    font-size: 1.1rem;
    font-weight: 500;
    margin-top: 0.5rem;
    color: #666;
    user-select: none;
}

.plugin-card {
    height: 9rem;
}

#marketplace-plugins-container {
    display: flex;
    flex-direction: column;
    width: 100%;
    height: calc(100vh - 16rem);
    overflow-y: auto;
    position: relative;
    /* 添加定位上下文 */
}

/* 将flex布局替换为grid布局 */
#marketplace-plugins-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(18rem, 1fr));
    /* 自动填充列 */
    gap: 16px;
    width: 100%;
    padding: 1rem;
    box-sizing: border-box;
}

/* 新增状态展示样式 */
.loading-indicator,
.error-message,
.no-data-message {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.2rem;
}

.error-message {
    color: #ff5252;
}

.no-data-message {
    color: #757575;
}
</style>