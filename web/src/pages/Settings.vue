<template>
  <PageTitle title="设置" @refresh="refresh" />

  <v-card id="settings-card">
    <v-tabs id="settings-tabs" v-model="proxy.$store.state.settingsPageTab" show-arrows center-active
      @update:model-value="onTabChange">
      <v-tooltip v-for="manager in managerList" :key="manager.name" :text="manager.description"
        location="top">
        <template v-slot:activator="{ props }">
          <v-tab v-bind="props" :value="manager.name">{{ manager.name }}</v-tab>
        </template>
      </v-tooltip>
    </v-tabs>
    <v-tabs-window id="settings-tab-window" v-model="proxy.$store.state.settingsPageTab">
      <v-tabs-window-item v-for="manager in managerList" :key="manager.name" :value="manager.name"
        class="config-tab-window">
        <v-card class="config-tab-toolbar">
          <v-tooltip :text="currentManagerSchema == null ? '仅配置文件管理器提供了 JSON Schema 时支持可视化配置' : '切换编辑模式'" location="top">
            <template v-slot:activator="{ props }">

              <v-btn-toggle id="config-type-toggle" color="primary" v-model="configType" mandatory v-bind="props" density="compact">

                <v-btn class="config-type-toggle-btn" value="ui" :readonly="currentManagerSchema == null" density="compact">
                  <v-icon>mdi-view-dashboard-edit-outline</v-icon>
                </v-btn>
                <v-btn class="config-type-toggle-btn" value="json" :readonly="currentManagerSchema == null" density="compact">
                  <v-icon>mdi-code-json</v-icon>
                </v-btn>
              </v-btn-toggle>
            </template>
          </v-tooltip>

          <div id="file-operation-toolbar">
            <v-btn @click="reset" color="warning" prepend-icon="mdi-undo" :disabled="!modified && configType == 'json'">重置</v-btn>
            <v-btn @click="saveAndApply" color="primary" prepend-icon="mdi-content-save-outline" :disabled="!modified && configType == 'json'">应用</v-btn>
          </div>
        </v-card>

        <div id="config-tab-content">

          <div id="config-tab-content-ui" v-if="configType == 'ui'">
            <v-form id="config-tab-content-ui-form">
              <vjsf id="config-tab-content-ui-form-vjsf" :schema="currentManagerSchema" v-model="currentManagerData" :options="VJSFOptions" />
            </v-form>
          </div>

          <v-card id="config-tab-content-json" v-if="configType == 'json'">
            <textarea id="config-tab-content-json-textarea" @input="onInput" v-model="currentManagerDataEditorString" />
          </v-card>
        </div>
      </v-tabs-window-item>
    </v-tabs-window>
  </v-card>

</template>

<script setup>

import PageTitle from '@/components/PageTitle.vue'
import { ref, getCurrentInstance, onMounted } from 'vue'

import Vjsf from '@koumoul/vjsf';

const { proxy } = getCurrentInstance()

const managerList = ref([])
const configType = ref('json')  // ui or json
const currentManager = ref(null)
const currentManagerData = ref({})
const currentManagerDataEditorString = ref('')
const currentManagerSchema = ref(null)
const modified = ref(false)

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

const refresh = () => {
  proxy.$axios.get('/settings').then(response => {
    managerList.value = response.data.data.managers

    if (proxy.$store.state.settingsPageTab != '') {
      fetchCurrentManagerData(proxy.$store.state.settingsPageTab)
    } else {
      proxy.$store.state.settingsPageTab = managerList.value[0].name
      fetchCurrentManagerData(proxy.$store.state.settingsPageTab)
    }

    firstJumpEditorAfterChangeTab()
  })
}

const onTabChange = (tab) => {
  fetchCurrentManagerData(tab)
  firstJumpEditorAfterChangeTab()
}

const firstJumpEditorAfterChangeTab = () => {
  if (currentManagerSchema.value != null) {
    configType.value = 'ui'
  } else {
    configType.value = 'json'
  }
}

const fetchCurrentManagerData = (tab) => {
  proxy.$axios.get(`/settings/${tab}`).then(response => {
    currentManager.value = response.data.data.manager
    currentManagerData.value = currentManager.value.data
    currentManagerDataEditorString.value = JSON.stringify(currentManager.value.data, null, 2)
    currentManagerSchema.value = currentManager.value.schema
  })
}

const onInput = () => {
  modified.value = true
}

const saveAndApply = () => {
  if (configType.value == 'json') {
    currentManagerData.value = JSON.parse(currentManagerDataEditorString.value)
  }

  proxy.$axios.put(`/settings/${currentManager.value.name}/data`, {
    data: currentManagerData.value
  }).then(response => {
    fetchCurrentManagerData(currentManager.value.name)
    modified.value = false
  })
}

const reset = () => {
  if (configType.value == 'json') {
    currentManagerData.value = JSON.stringify(currentManager.value.data, null, 2)
  } else {
    fetchCurrentManagerData(currentManager.value.name)
  }
  modified.value = false
}

onMounted(async () => {
  refresh()
})

</script>

<style scoped>
#settings-card {
  margin: 1rem;
  height: calc(100% - 5rem);
  /* max-height: calc(100% - 5rem); */
  display: flex;
  flex-direction: column;
  overflow: hidden;
  /* background-color: #f0f0f0; */
}

#settings-tabs {
  height: 3rem;
  overflow: hidden;
}

#settings-tab-window {
  height: calc(100vh - 9rem);
  overflow: hidden;
  /* background-color: aqua; */
}

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

#config-tab-content-json-textarea {
  width: 100%;
  height: 100%;
  resize: none;
  padding: 0.6rem;
  background-color: #f0f0f0;
  border: none;
  outline: none;
  appearance: none;
  /*字间隔增大*/
  letter-spacing: 0.05rem;
  line-height: 1.6rem;
  text-wrap: nowrap;
}
</style>