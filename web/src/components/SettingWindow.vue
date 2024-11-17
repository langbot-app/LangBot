<template>
    <v-card class="config-tab-toolbar">
        <v-tooltip :text="currentManagerSchema == null ? '仅配置文件管理器提供了 JSON Schema 时支持可视化配置' : '切换编辑模式'" location="top">
            <template v-slot:activator="{ props }">

                <v-btn-toggle id="config-type-toggle" color="primary" v-model="configType" mandatory v-bind="props"
                    density="compact">

                    <v-btn class="config-type-toggle-btn" value="ui" :readonly="currentManagerSchema == null"
                        density="compact">
                        <v-icon>mdi-view-dashboard-edit-outline</v-icon>
                    </v-btn>
                    <v-btn class="config-type-toggle-btn" value="json" :readonly="currentManagerSchema == null"
                        density="compact">
                        <v-icon>mdi-code-json</v-icon>
                    </v-btn>
                </v-btn-toggle>
            </template>
        </v-tooltip>

        <div id="file-operation-toolbar">
            <v-btn @click="reset" color="warning" prepend-icon="mdi-undo"
                :disabled="!modified && configType == 'json'">重置</v-btn>
            <v-btn @click="saveAndApply" color="primary" prepend-icon="mdi-content-save-outline"
                :disabled="!modified && configType == 'json'">应用</v-btn>
        </div>
    </v-card>

    <div id="config-tab-content">

        <div id="config-tab-content-ui" v-if="configType == 'ui'">
            <v-form id="config-tab-content-ui-form">
                <vjsf id="config-tab-content-ui-form-vjsf" :schema="currentManagerSchema" v-model="currentManagerData"
                    :options="VJSFOptions" />
            </v-form>
        </div>

        <v-card id="config-tab-content-json" v-if="configType == 'json'">
            <JsonEditorVue id="config-tab-content-json-json-editor-vue" v-model="currentManagerData" mode="text"
                @change="onInput" />
        </v-card>

        <div id="config-tab-json-doc-link"
            v-if="configType == 'json' && currentManagerDocLink != undefined && currentManagerDocLink != ''">*配置文件格式请查看
            <a :href="currentManagerDocLink" target="_blank">文档</a>
        </div>
    </div>
</template>

<script setup>

import { ref, getCurrentInstance, onMounted, inject } from 'vue'
import JsonEditorVue from 'json-editor-vue';

import Vjsf from '@koumoul/vjsf';

const VJSFOptions = {
    "context": {},
    "width": 1208,
    "readOnly": false,
    "summary": false,
    "density": "comfortable",
    "indent": true,
    "titleDepth": 4,
    "validateOn": "input",
    "initialValidation": "withData",
    "updateOn": "input",
    "debounceInputMs": 300,
    "defaultOn": "empty",
    "removeAdditional": "error",
    "autofocus": false,
    "readOnlyPropertiesMode": "show",
    "pluginsOptions": {},
    "locale": "en",
    "messages": {
        "errorOneOf": "请选择一个",
        "errorRequired": "必填信息",
        "addItem": "添加",
        "delete": "删除",
        "edit": "编辑",
        "close": "关闭",
        "duplicate": "复制",
        "sort": "排序",
        "up": "向上移动",
        "down": "向下移动",
        "showHelp": "显示帮助信息",
        "mdeLink1": "[链接标题",
        "mdeLink2": "](链接地址)",
        "mdeImg1": "![](",
        "mdeImg2": "图片地址)",
        "mdeTable1": "",
        "mdeTable2": "\n\n| 列 1 | 列 2 | 列 3 |\n| -------- | -------- | -------- |\n| 文本     | 文本     | 文本     |\n\n",
        "bold": "加粗",
        "italic": "斜体",
        "heading": "标题",
        "quote": "引用",
        "unorderedList": "无序列表",
        "orderedList": "有序列表",
        "createLink": "创建链接",
        "insertImage": "插入图片",
        "createTable": "创建表格",
        "preview": "预览",
        "mdeGuide": "文档",
        "undo": "撤销",
        "redo": "重做"
    }
}

const snackbar = inject('snackbar');

const { proxy } = getCurrentInstance()

const props = defineProps({
    name: String
})

const currentManagerData = ref({})
const currentManagerSchema = ref(null)
const currentManagerDocLink = ref(null)
const configType = ref('')
const modified = ref(false)

const fetchCurrentManagerData = (name) => {
    console.log(name)
    return new Promise((resolve, reject) => {
        proxy.$axios.get(`/settings/${name}`).then(response => {
            console.log(response.data.data)
            currentManagerData.value = response.data.data.manager.data
            currentManagerSchema.value = response.data.data.manager.schema
            currentManagerDocLink.value = response.data.data.manager.doc_link
            resolve()
        }).catch(error => {
            snackbar.error(error)
            reject(error)
        })
    })
}

const autoSwitchConfigType = () => {
    console.log(currentManagerSchema == null)
    if (currentManagerSchema.value == null) {
        configType.value = 'json'
    } else {
        configType.value = 'ui'
    }
}


const isJsonValid = ref(true)
const errorMessage = ref('')

const checkJsonValid = () => {
    try {
        JSON.parse(currentManagerData.value)
        isJsonValid.value = true
        errorMessage.value = ''
    } catch (error) {
        isJsonValid.value = false
        errorMessage.value = error.message
    }
}

const onInput = () => {
    modified.value = true
    checkJsonValid()
}

const saveAndApply = () => {
    if (configType.value == 'json') {
        checkJsonValid()
    }
    if (!isJsonValid.value) {
        snackbar.error('JSON 格式不正确: ' + errorMessage.value)
        return
    }
    if (configType.value == 'json') {
        currentManagerData.value = JSON.parse(currentManagerData.value)
    }

    proxy.$axios.put(`/settings/${props.name}/data`, {
        data: currentManagerData.value
    }).then(response => {
        if (response.data.code != 0) {
            snackbar.error(response.data.msg)
            return
        }
        fetchCurrentManagerData(props.name).then(() => {
            modified.value = false
            snackbar.success('应用成功')
        }).catch(error => {
            snackbar.error(error)
        })
    })
}

const reset = () => {
    fetchCurrentManagerData(props.name).then(() => {
        snackbar.success('重置成功')
        modified.value = false
    })
}

onMounted(() => {
    console.log(props.name)
    fetchCurrentManagerData(props.name).then(() => {
        autoSwitchConfigType()
    })
})
</script>

<style scoped>
.config-tab-window {
    overflow: hidden;
}

.config-tab-toolbar {
    margin: 0.5rem;
    height: 3.2rem;
    display: flex;
    flex-direction: row;
    justify-content: space-between;
    align-items: center;
}

#file-operation-toolbar {
    display: flex;
    flex-direction: row;
    justify-content: flex-end;
    align-items: center;
    gap: 0.5rem;
    margin-right: 0.5rem;
}

#config-type-toggle {
    margin: 0.5rem;
    box-shadow: 0 0 0 2px #dddddd;
}

#config-tab-content {
    margin: 0.2rem;
    height: calc(100% - 1rem);
    overflow: hidden;
}

#config-tab-content-ui {
    margin: 0.5rem;
    height: calc(100vh - 15rem);
    margin-top: 1rem;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
}

#config-tab-content-ui-form {
    height: 100%;
    width: calc(100% - 1.5rem);
    margin-left: 0.5rem;
    overflow-y: auto;
}

#config-tab-content-ui-form-vjsf {
    height: 100%;
    width: calc(100% - 1rem);
}

#config-tab-content-json {
    margin: 0.5rem;
    height: calc(100vh - 16rem);
    margin-top: 1rem;
}

#config-tab-content-json-json-editor-vue {
    height: 100%;
    width: 100%;
}

#config-tab-json-doc-link {
    margin: 0rem;
    margin-left: 0.6rem;
    height: 1.5rem;
    margin-top: 0.2rem;
    font-size: 0.8rem;
    color: rgb(26, 98, 214);
}
</style>