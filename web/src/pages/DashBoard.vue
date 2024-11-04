<template>
    <PageTitle title="仪表盘" @refresh="refresh" />

    <div id="dashboard-content">
        <div id="first-row">
            <v-card id="basic-analysis-number-card">
                <v-card-title class="content-card-title">
                    <v-icon class="content-card-title-icon" icon="mdi-chart-line" />
                    基础数据
                </v-card-title>

                <div id="basic-analysis-number-card-content">
                    <NumberFieldData title="活跃会话" :number="100" />
                    <NumberFieldData title="对话总数" :number="100" />
                    <NumberFieldData title="请求总数" :number="100" />
                </div>
            </v-card>

            <v-card id="message-platform-card">
                <v-card-title class="content-card-title">
                    <v-icon class="content-card-title-icon" icon="mdi-message-outline" />
                    消息平台
                </v-card-title>

                <div id="message-platform-card-content">
                    <NumberFieldData title="已启用" :number="1" link="/platforms" linkText="更改配置" />
                </div>
            </v-card>

            <v-card id="plugins-amount-card">
                <v-card-title class="content-card-title">
                    <v-icon class="content-card-title-icon" icon="mdi-puzzle-outline" />
                    插件数量
                </v-card-title>

                <div id="plugins-amount-card-content">
                    <NumberFieldData title="已加载" :number="3" link="/plugins" linkText="管理插件" />
                </div>
            </v-card>
        </div>
    </div>
</template>

<script setup>

import PageTitle from '@/components/PageTitle.vue'
import NumberFieldData from '@/components/NumberFieldData.vue'

import { ref, onMounted } from 'vue'

</script>

<style scoped>
#dashboard-content {
    display: table;
    width: 100%;
    padding-inline: 1rem;
    margin-top: 1rem;
    overflow-x: auto;
}

#first-row {
    display: flex;
    flex-direction: row;
    justify-content: flex-start;
    gap: 1rem;
}

#basic-analysis-number-card {
    width: 35%;
    min-width: 16rem;
    padding-bottom: 0.5rem;
}

#basic-analysis-number-card-content {
    display: flex;
    flex-direction: row;
    justify-content: space-evenly;
}

.content-card-title {
    font-size: 1rem;
    font-weight: 600;
}

.content-card-title-icon {
    font-size: 1.2rem;
}

#message-platform-card {
    width: 15%;
    min-width: 6rem;
    padding-bottom: 0.7rem;
}

#plugins-amount-card {
    width: 15%;
    min-width: 6rem;
    padding-bottom: 0.7rem;
}
</style>