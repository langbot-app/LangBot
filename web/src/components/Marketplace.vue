<template>
    <div id="marketplace-container">
        <div id="marketplace-search-bar">
            
            <span style="width: 14rem;">
                <v-text-field id="marketplace-search-bar-search-input" variant="solo" v-model="proxy.$store.state.marketplaceParams.query" label="搜索"
                    density="compact" @update:model-value="updateSearch" />
            </span>
            <!--下拉选择排序-->
            <span style="width: 10rem;">
                <v-select id="marketplace-search-bar-sort-select" v-model="sort" :items="sortItems" variant="solo"
                    label="排序" density="compact" @update:model-value="updateSort" />
            </span>
            <span style="margin-left: 1rem;">
                <div id="marketplace-search-bar-total-plugins-count">
                    共 {{ proxy.$store.state.marketplaceTotalPluginsCount }} 个插件
                </div>
            </span>
            <span style="margin-left: 1rem;">
                <!-- 分页 -->
                <v-pagination style="width: 14rem;" v-model="proxy.$store.state.marketplaceParams.page"
                    :length="proxy.$store.state.marketplaceTotalPages" variant="solo" density="compact"
                    total-visible="4" @update:model-value="updatePage" />
            </span>
        </div>
        <div id="marketplace-plugins-container" ref="pluginsContainer">
            <div id="marketplace-plugins-container-inner">
                <MarketPluginCard v-for="plugin in proxy.$store.state.marketplacePlugins" :key="plugin.id" :plugin="plugin" @install="installPlugin" />
            </div>
        </div>
    </div>
</template>

<script setup>
import MarketPluginCard from './MarketPluginCard.vue'

import { ref, getCurrentInstance, onMounted } from 'vue'

import { inject } from "vue";

const snackbar = inject('snackbar');

const { proxy } = getCurrentInstance()

const pluginsContainer = ref(null)

const sortItems = ref([
    '最近新增',
    '最多星标',
    '最近更新',
])

const sortParams = ref({
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
})

const sort = ref(sortItems.value[0])

proxy.$store.state.marketplaceParams.sort_by = sortParams.value[sort.value].sort_by
proxy.$store.state.marketplaceParams.sort_order = sortParams.value[sort.value].sort_order

const updateSort = (value) => {
    console.log(value)
    proxy.$store.state.marketplaceParams.sort_by = sortParams.value[value].sort_by
    proxy.$store.state.marketplaceParams.sort_order = sortParams.value[value].sort_order
    proxy.$store.state.marketplaceParams.page = 1

    console.log(proxy.$store.state.marketplaceParams)
    fetchMarketplacePlugins()
}

const updatePage = (value) => {
    proxy.$store.state.marketplaceParams.page = value
    fetchMarketplacePlugins()
}

const updateSearch = (value) => {
    console.log(value)
    proxy.$store.state.marketplaceParams.query = value
    proxy.$store.state.marketplaceParams.page = 1
    fetchMarketplacePlugins()
}

const calculatePluginsPerPage = () => {
    if (!pluginsContainer.value) return 10
    
    const containerWidth = pluginsContainer.value.clientWidth
    const containerHeight = pluginsContainer.value.clientHeight

    console.log(containerWidth, containerHeight)
    
    // 每个卡片宽度18rem + gap 16px
    const cardWidth = 18 * 16 + 16 // rem转px
    // 每个卡片高度9rem + gap 16px
    const cardHeight = 9 * 16 + 16
    
    // 计算每行可以放几个卡片
    const cardsPerRow = Math.floor(containerWidth / cardWidth)
    // 计算每行可以放几行
    const rows = Math.floor(containerHeight / cardHeight)
    
    // 计算每页总数
    const perPage = cardsPerRow * rows
    
    proxy.$store.state.marketplaceParams.per_page = perPage > 0 ? perPage : 10
}

const fetchMarketplacePlugins = async () => {
    calculatePluginsPerPage()
    proxy.$axios.post('https://space.langbot.app/api/v1/market/plugins', {
        query: proxy.$store.state.marketplaceParams.query,
        sort_by: proxy.$store.state.marketplaceParams.sort_by,
        sort_order: proxy.$store.state.marketplaceParams.sort_order,
        page: proxy.$store.state.marketplaceParams.page,
        page_size: proxy.$store.state.marketplaceParams.per_page,
    }).then(response => {
        console.log(response.data)
        if (response.data.code != 0) {
            snackbar.error(response.data.msg)
            return
        }

        // 解析出 name 和 author
        response.data.data.plugins.forEach(plugin => {
            plugin.name = plugin.repository.split('/')[2]
            plugin.author = plugin.repository.split('/')[1]
        })

        proxy.$store.state.marketplacePlugins = response.data.data.plugins
        proxy.$store.state.marketplaceTotalPluginsCount = response.data.data.total

        let totalPages = Math.floor(response.data.data.total / proxy.$store.state.marketplaceParams.per_page)
        if (response.data.data.total % proxy.$store.state.marketplaceParams.per_page != 0) {
            totalPages += 1
        }
        proxy.$store.state.marketplaceTotalPages = totalPages
    }).catch(error => {
        snackbar.error(error)
    })
}

onMounted(() => {
    calculatePluginsPerPage()
    fetchMarketplacePlugins()
    
    // 监听窗口大小变化
    window.addEventListener('resize', () => {
        calculatePluginsPerPage()
        fetchMarketplacePlugins()
    })
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
    width: 18rem;
    height: 9rem;
}

#marketplace-plugins-container {
    display: flex;
    flex-direction: row;
    justify-content: flex-start;
    flex-wrap: wrap;
    gap: 16px;
    margin-inline: 0rem;
    width: 100%;
    height: calc(100vh - 16rem);
    overflow-y: auto;
}

#marketplace-plugins-container-inner {
    display: flex;
    flex-direction: row;
    justify-content: flex-start;
    flex-wrap: wrap;
    gap: 16px;
}
</style>